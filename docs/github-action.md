# GitHub Action

RagDiff runs your app at the PR's base and head revisions, compares scores per
question, and posts one comment (updated on every push) with the verdict, the
culprit and a suggested fix. The check fails when the verdict is `fail`.

## Use it

```yaml
name: RagDiff
on: pull_request

permissions:
  contents: read
  pull-requests: write   # to post the comment

jobs:
  ragdiff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # both revisions must be in the clone
      - uses: GaneshAmpcus/RagDiff@v0.1.0
        with:
          config: evals.yaml
          extras: llm,metrics     # only if you use LiteLLM / Ragas metrics
          install-command: pip install -r requirements.txt
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

## Inputs

| Input | Default | Purpose |
| --- | --- | --- |
| `config` | `evals.yaml` | Eval config, relative to `working-directory` |
| `base-ref` / `head-ref` | PR base / head SHA | Revisions to compare |
| `working-directory` | `.` | Where to run |
| `python-version` | `3.11` | |
| `extras` | empty | RagDiff extras, e.g. `llm,metrics` |
| `install-command` | empty | Installs your app's dependencies |
| `comment` | `true` | Post/update the PR comment |
| `fail-on-regression` | `true` | Fail the step on a `fail` verdict |
| `github-token` | `github.token` | Needs `pull-requests: write` |

Outputs: `verdict` (`pass`, `fail`, `inconclusive`) and `culprit`.

## Things to know

- **Dataset size.** The verdict uses a 95% interval over per-question deltas.
  With only a handful of questions the interval is wide and a real drop shows
  as `inconclusive` (which does not fail the check). Aim for 10+ questions.
- **Forks.** PRs from forks get a read-only token: the report still appears in
  the job summary but the comment is skipped with a warning.
- **Attribution.** Git-revision runs get Tier 1 attribution (retrieval vs
  generation). Tier 2 ablation needs a variant comparison.
- **Secrets.** Your app runs on the CI runner with whatever environment you
  give the step. Do not run it on untrusted fork code with secrets.
- **Not yet.** The comment does not link to a web UI (Phase 5).
- **Runners.** Linux (`ubuntu-latest`) only.

## Try it locally

```bash
ragdiff compare --config evals.yaml --base-ref main --head-ref HEAD \
  --report-path report.md
```
