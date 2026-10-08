import json
from pathlib import Path

from typer.testing import CliRunner

from ragdiff.bootstrap.dataset import DatasetCase
from ragdiff.cli.main import app
from ragdiff.contract import RunOutput
from ragdiff.metrics.lexical import AnswerContainsReference, ContextContainsReference

CONFIG = """\
app: sample_rag.app:run
dataset: {dataset}
metrics: [context_contains_reference]
thresholds:
  context_contains_reference: -0.05
tracked_config:
  retrieval: [chunk_size, top_k]
variants:
  - name: baseline
    config: {{chunk_size: 800, top_k: 3}}
  - name: candidate
    config: {{chunk_size: 12, top_k: 3}}
"""


def _dataset(path: Path) -> None:
    rows = [
        ("What does RagDiff provide tools and interfaces for", "evaluating retrieval-augmented generation applications"),
        ("What is RagDiff used to evaluate", "retrieval-augmented generation applications"),
        ("Which kind of applications does RagDiff evaluate", "retrieval-augmented generation applications"),
        ("What do applications return to RagDiff", "an answer and may also return retrieved contexts and metadata"),
        ("What may applications also return besides an answer", "retrieved contexts and metadata"),
        ("Do applications return retrieved contexts and metadata", "an answer and may also return retrieved contexts and metadata"),
    ]  # fmt: skip
    path.write_text(
        "".join(
            json.dumps({"question": q, "reference": r, "status": "approved"}) + "\n"
            for q, r in rows
        ),
        encoding="utf-8",
    )


def test_cli_compare_fails_gate_and_names_retrieval(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / "examples"))
    dataset = tmp_path / "dataset.jsonl"
    _dataset(dataset)
    config = tmp_path / "evals.yaml"
    config.write_text(CONFIG.format(dataset=dataset.as_posix()), encoding="utf-8")
    report = tmp_path / "out" / "report.md"

    result = CliRunner().invoke(
        app,
        [
            "compare", "--config", str(config),
            "--base", "baseline", "--head", "candidate",
            "--report-path", str(report),
        ],
    )  # fmt: skip

    assert result.exit_code == 1, result.output
    assert "Verdict: fail" in result.output
    assert "Culprit: retrieval" in result.output
    text = report.read_text(encoding="utf-8")
    assert "## Attribution" in text and "chunk_size" in text


def test_lexical_metrics_score_token_recall() -> None:
    case = DatasetCase(question="q", reference="refund window thirty days")
    output = RunOutput(answer="refund window", contexts=["thirty days policy"])

    assert AnswerContainsReference().score(case, output) == 0.5
    assert ContextContainsReference().score(case, output) == 0.5
