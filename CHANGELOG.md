# Changelog

## Current state (v0.1.0, 2026-10-08)

| Phase | Status | Notes |
| --- | --- | --- |
| 0 Foundations | Done | Packaging, CI, config schema, app contract, sample app, docker-compose (postgres, redis only) |
| 1 Bootstrap + metrics | Done | LLM client + disk cache, synthetic Q&A, Ragas adapters, `baseline` |
| 2 Base vs PR comparison | Done (20 tests, ruff and mypy clean) | Paired per-question stats, CI-based verdict, git-ref isolation, `ragdiff compare` |
| 3 Attribution | Done for variant comparisons; git-ref runs get Tier 1 only | Tier 1 context diff, Tier 2 ablation, suggested fixes, `tracked_config` |
| 4 API/DB/workers | Not started | No FastAPI, SQLAlchemy, Alembic, Celery |
| 5 UI | Not started | |
| 6 GitHub integration | Early version in v0.1.0 | Composite action (`action.yml`): runs compare, one updatable PR comment, merge gate. No UI link yet; not yet run on GitHub |
| 7 Pilot and polish | Not started | |

Known gaps vs `Project_implementaion.md`:
- LLM cache is on disk, not Redis (fine for local-first; revisit in Phase 4).
- `repeats` defaults to 1 (plan example uses 3).
- Tier 2 ablation works only for variant comparisons (config-driven); `--base-ref/--head-ref` runs have no config diff, so they get Tier 1 (retrieval vs generation).
- Demo PRs from the plan (chunk size, prompt, model swap) are covered by tests with a toy app, not yet by a real RAG repo.
- Synthetic cases are `pending` but still run; there is no review step yet.
- Ragas scores one case per `evaluate()` call (slow on large datasets).
- Ablation helper is a generic leave-one-out, not the "swap base prompt / base model" Tier 2 from the plan.

Next: Phase 4 (SQLAlchemy models, Alembic, FastAPI, Celery worker). Failure clustering (stretch) is not done.

## 0.1.0 (2026-10-08): CLI + GitHub Action

- GitHub Action (`action.yml`, `scripts/post_comment.sh`): compares PR base vs
  head by git revision, writes the job summary, posts/updates one PR comment,
  fails the check on a `fail` verdict. Docs in `docs/github-action.md`.
- Dogfood workflow `.github/workflows/ragdiff.yml` with a keyless demo config
  (`examples/sample_rag/evals.ci.yaml`, `dataset.jsonl`).
- `ragdiff compare --report-path` writes the Markdown report to a file.
- New built-in LLM-free metrics: `answer_contains_reference` and
  `context_contains_reference` (token recall of the reference answer).
- `.gitattributes` keeps `*.sh` / `*.yml` on LF line endings.
- Tests: `test_cli_compare.py` (CLI gate exit code, culprit, report file).
- Phase 3: new `tracked_config` (retrieval / prompt / model -> config keys).
- Phase 3: Tier 1 compares retrieved contexts on regressed questions; >= 70%
  changed -> retrieval, <= 30% -> prompt/model, otherwise ambiguous.
- Phase 3: Tier 2 re-runs head on regressed questions with one factor reverted
  to base; the factor recovering >= 50% of the drop is the culprit.
- Phase 3: one-line suggested fix per culprit; report, `attribution.json` and
  `ragdiff compare` show culprit, confidence and fix.
- Behaviour change: `CompareReport.culprit` is now a factor (or None) and is
  only set when the verdict is `fail`; it was the metric with the largest drop.
- Phase 3: new `tests/unit/test_phase3.py`.
- Phase 2: comparison is paired by question; repeats are averaged per question,
  then a 95% t-interval is computed over per-question deltas.
- Phase 2: verdict fails only when the delta is below the threshold and the
  interval is entirely below zero; a breach inside the noise is `inconclusive`.
  With a single question the point estimate decides (old behaviour).
- Phase 2: each metric now reports `ci_low`, `ci_high`, `significant`,
  `questions`, `regressed` (questions down by >= 0.05) and `improved`.
- Phase 2: Markdown report shows the CI and lists regressed questions.
- Phase 2: `RagDiff.compare_refs()` runs base and head git revisions in
  separate worktrees and processes (`runner/worker.py`,
  `runner/subprocess_runner.py`); scoring stays in the parent.
- Phase 2: new `ragdiff compare` command (variants or `--base-ref/--head-ref`);
  exits 1 when the verdict is `fail`. New config key `app_dir`.
- Phase 2: new `tests/unit/test_phase2.py` (stats, verdicts, git-ref run).
- Lint fixes: `Optional` -> `X | None`, explicit `check=False`, `writelines`,
  merged nested `if` in `bootstrap/generator.py`.
- Phase 1: synthetic Q&A generation with reference answers, case `status` /
  `source` fields (rejected cases are skipped), built-in Ragas metric adapters
  with name aliases and optional pinned judge model, `RagDiff.baseline()` and
  `ragdiff baseline`, `entrypoint` accepted as an alias for `app`.
- Phase 0: `docker-compose.yml` (postgres, redis); sample app now does real
  keyword retrieval driven by `chunk_size` / `top_k`.
- Add the initial `src/`-layout RagDiff library, CLI, local storage and cache,
  protocol-based integrations, sample app, and starter tests.
