# RagDiff

RagDiff is a Python library and CLI scaffold for evaluating and comparing
retrieval-augmented generation (RAG) applications. Its `src/` package layout,
protocol-based integrations, and local filesystem defaults keep the core
installable without Redis, Postgres, or a hosted service.

## Install

```bash
pip install -e .
```

Optional provider integrations are installed separately:

```bash
pip install -e ".[llm]"
pip install -e ".[metrics]"
```

## Quick start

Create an evaluation config and dataset (JSON Lines, one object per line):

```yaml
app: sample_rag.app:run
dataset: .ragdiff/datasets/dataset.jsonl
repeats: 1
metrics: []
thresholds: {}
```

The app entrypoint receives a question and a config mapping, and returns either
a `RunOutput` or a mapping containing an `answer` and optional `contexts`:

```python
from ragdiff import RunOutput

def run(question: str, config: dict) -> RunOutput:
    return RunOutput(answer=f"Answer to: {question}")
```

For API comparisons, define two variants in `evals.yaml`; `base` and `head`
refer to these variant names:

```yaml
app: sample_rag.app:run
dataset: .ragdiff/datasets/dataset.jsonl
variants:
  - name: baseline
  - name: candidate
```

```python
from ragdiff import RagDiff

rd = RagDiff.from_config("evals.yaml")
rd.bootstrap()
report = rd.compare(base="baseline", head="candidate")
print(report.verdict, report.culprit)
```

Useful initial commands:

```bash
ragdiff --help
ragdiff init
ragdiff bootstrap --config evals.yaml
ragdiff run --config evals.yaml
ragdiff report --run-id <run-id>
```

The CLI accepts injected integrations through the Python API; external LLM and
Ragas adapters are optional extras. See [examples/sample_rag](examples/sample_rag)
for a small app and evaluation config.

## Architecture

The package is organized into `config`, `llm`, `bootstrap`, `metrics`, `runner`,
`compare`, `attribution`, `report`, `storage`, `observability`, `cli`, and
`utils`. Dependencies should flow from the CLI and orchestration layers toward
the lower-level interfaces; lower layers do not import the CLI.

The default filesystem store writes datasets and run artifacts under
`.ragdiff/`. The library attaches a `NullHandler` only; applications decide
where logs go, while the CLI may explicitly configure console and per-run JSONL
logging.

## Development

```bash
make test
make lint
make type-check
```

See [CHANGELOG.md](CHANGELOG.md) for the initial scaffold scope.
