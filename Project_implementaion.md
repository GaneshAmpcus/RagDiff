# RAGDiff (working name)

**CI for RAG apps: bootstrap your evals, catch regressions on every PR, and find out *why* quality dropped.**

## The problem

You change a prompt, a chunk size, or a model in your RAG app. Did answers get worse? Where? Because of what?

- Most teams have no eval set, so they eyeball a few answers.
- Teams that do have evals get a score ("faithfulness -6%") but still dig through traces to find the cause.

## What RAGDiff does

1. **Bootstraps** an eval pipeline for your RAG app (dataset + metrics + config) with no labeled data needed.
2. **Compares** base vs PR on the same questions, with repeated runs so only real changes are flagged.
3. **Attributes** the cause: retrieval, prompt, or model.
4. **Reports** on the PR (comment + merge gate) and in a web UI.

### Example

A PR changes `chunk_size` from 800 to 400.

| Typical eval bot | RAGDiff |
|---|---|
| Faithfulness: 0.91 -> 0.85 (-6%) | Faithfulness dropped 6%. **Cause: retrieval.** |
| | Context recall fell 0.88 -> 0.74; 9 of 11 regressed questions lost the chunk holding the answer. |
| | "What is the refund window?" used to retrieve the policy chunk; now it retrieves only the header. |
| | Suggested fix: revert `chunk_size` or raise `top_k` to 6. |

## Principles (what makes it useful, not a demo)

- **Local-first:** `pip install ragdiff` works with no server. The server and UI add history and team review.
- **Low noise:** repeated runs, significance checks, pinned judge model and prompts.
- **Low cost:** Redis cache for LLM calls; attribution runs only on regressed questions; cheap checks before expensive ones.
- **Private:** self-hostable with docker-compose; no data leaves the team's infra except calls to their chosen LLM provider.
- **Framework-agnostic:** works with LangChain, LlamaIndex, or raw SDK apps through one contract.

## Scope

- **Python RAG apps only.**
- Three change types: retrieval config, prompt, model.
- Out of scope for now: other languages, agent/tool-call evals, multi-tenant auth, billing.

## The app contract

The user's app exposes one function. The `config` argument is what lets RAGDiff test one change at a time.

```python
def run(question: str, config: dict | None = None) -> dict:
    # returns {"answer": str, "contexts": list[str]}
```

`evals.yaml` in the user's repo:

```yaml
entrypoint: app.rag:run
dataset: evals/dataset.jsonl
metrics: [faithfulness, context_recall, answer_relevance]
repeats: 3
thresholds:
  faithfulness: -0.03
tracked_config:
  retrieval: [chunk_size, top_k, embedding_model]
  prompt: prompts/system.txt
  model: [llm_model, temperature]
```

## Attribution (the differentiator)

- **Tier 1, free:** compare retrieved contexts between base and PR.
  - Contexts changed and recall dropped -> **retrieval**.
  - Contexts identical but the answer changed -> **prompt or model**.
- **Tier 2, ablation (only for ambiguous cases):** run the PR code with the base prompt, then with the base model, and see which swap restores the score.
- **Failure clustering (stretch):** group regressed questions by theme ("all date questions got worse").

## Architecture

```
GitHub PR
   |
   v
GitHub Action / CLI  (ragdiff run)
   |  bootstrap -> run base & PR (x3) -> score -> attribute
   |  LLM calls: LiteLLM, cached in Redis
   v
FastAPI  --enqueue-->  Redis  -->  Celery worker (runs in Docker sandbox)
   |
   v
Postgres  <---  Streamlit UI (runs, diffs, culprit, dataset review)
```

## Stack

- **API:** FastAPI, SQLAlchemy, Alembic
- **Data:** Postgres; Redis (Celery broker + LLM cache)
- **Jobs:** Celery
- **LLM access:** LiteLLM behind an internal `LLMClient` interface (no per-provider logic, no LangChain)
- **Metrics:** Ragas behind an internal `Metric` interface (pin the version)
- **CLI:** Typer
- **UI:** Streamlit
- **Infra:** Docker, docker-compose

## Agents: where they are and aren't used

- **Core pipeline (run, score, attribute): no agents.** It is a fixed algorithm; agents would add cost and non-determinism.
- **Bootstrapper: one agent (LangGraph optional).** It reads the repo, finds the entrypoint, vector store, and prompt files, and drafts `evals.yaml`. The dev reviews and approves.
- **Later:** a skill file that teaches a dev's coding agent how to add eval cases and run RAGDiff.

## Data model

| Table | Key fields |
|---|---|
| `projects` | id, name, repo, config_path |
| `datasets` | id, project_id, version |
| `eval_cases` | id, dataset_id, question, expected_answer, source (synthetic / manual / production), status (pending / approved / rejected) |
| `runs` | id, project_id, pr_number, base_sha, head_sha, status, verdict, culprit, cost, created_at |
| `run_results` | id, run_id, case_id, variant (base / pr / ablation), answer, contexts, scores (JSON) |
| `attributions` | id, run_id, tier (1 / 2), factor (retrieval / prompt / model), evidence (JSON), confidence |

## Phases (about 28 days)

The earlier 15-day estimate no longer fits once bootstrap, Redis, Docker, the API, and the UI are in scope. A usable CLI exists after Phase 3.

### Phase 0: Foundations (Days 1-2)
- Repo, packaging, lint, CI skeleton, docker-compose (api, worker, postgres, redis).
- `evals.yaml` schema (Pydantic) and the `run(question, config)` contract.
- Sample RAG app with ~20 docs.
- **Done when:** `ragdiff run` loads config and calls the sample app.

### Phase 1: Bootstrap + metrics (Days 3-6)
- `LLMClient` over LiteLLM with a Redis cache.
- Dataset generator: docs/vector store -> synthetic Q&A -> reviewable `dataset.jsonl`.
- Ragas metrics behind the `Metric` interface; reference-free metrics first (faithfulness, answer relevance).
- **Done when:** one command takes a RAG repo from zero to a scored baseline.

### Phase 2: Base vs PR comparison (Days 7-10)
- Run base and head in isolated environments; 3 repeats per question.
- Statistical diff and pass/fail verdict from thresholds.
- **Done when:** a known bad change is flagged and a harmless change is not.

### Phase 3: Attribution (Days 11-14)
- Tier 1 context-diff attribution, then Tier 2 ablation for ambiguous cases.
- One-line suggested fix per culprit type.
- **Done when:** three demo PRs (chunk size, prompt, model swap) get the correct culprit.
- **Checkpoint: ship v0.1 as a CLI + GitHub Action here and get early feedback.**

### Phase 4: API, DB, and workers (Days 15-18)
- SQLAlchemy models and Alembic migrations.
- FastAPI endpoints: projects, runs, results, dataset review.
- Celery worker with Redis; CLI can push results to the API.
- **Done when:** a run is queued, executed in Docker, stored, and retrievable.

### Phase 5: UI (Days 19-23)
- Runs list with verdict and culprit.
- Run detail: metric table, base vs PR answers side by side, retrieved contexts, attribution evidence.
- Dataset review page: approve or reject synthetic cases; add a case from a failure.
- **Done when:** a reviewer understands a regression without opening logs.

### Phase 6: GitHub integration (Days 24-26)
- Action that runs on PRs, posts or updates one comment with a link to the UI, and gates the merge.
- **Done when:** opening a PR on the demo repo produces the comment automatically.

### Phase 7: Pilot and polish (Days 27-28+)
- Run on 3 real RAG repos (your own, plus two from friends or open source).
- Fix setup friction, noise, and cost problems they surface.
- Quickstart docs and a short demo video.
- **Done when:** a new user goes from install to a PR comment in under 30 minutes.

## Cutting scope

Drop in this order if time runs short: failure clustering, dataset review page (use a file), Streamlit polish, Postgres (use SQLite). Never cut Phase 3.

## Risks

- **Cost:** controlled by the Redis cache, Tier 1 attribution, and ablating only regressed questions.
- **Judge noise:** pinned judge model and prompts, repeated runs.
- **Running user code:** Docker sandbox, secrets passed as env vars only; stronger isolation later.
- **Ragas API changes:** pinned version behind the `Metric` interface.
- **Adoption:** validate in the pilot before adding features.
