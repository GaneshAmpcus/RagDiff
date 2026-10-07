# Architecture

RagDiff uses a `src/` package layout and separates orchestration from
replaceable integrations:

- `config`, `contract`, `errors`, and `utils` define shared types and helpers.
- `bootstrap` ingests local documents and reads/writes JSONL datasets.
- `llm`, `metrics`, `storage`, and cache interfaces isolate external services.
- `runner` executes app variants; `compare` summarizes their metric scores.
- `attribution` and `report` derive and render run artifacts.
- `observability` supplies opt-in logging; `cli` is the outermost entrypoint.

The filesystem storage and disk cache need no external services. Optional
provider packages are loaded lazily and report installation guidance when
needed. The API expects comparison variant names to be configured in YAML;
Git worktree isolation is supplied separately for callers that need it.
