import json

import pytest

from ragdiff import RagDiff
from ragdiff.bootstrap.dataset import DatasetCase, read_dataset, runnable_cases
from ragdiff.bootstrap.generator import generate_qa_pairs
from ragdiff.config.schema import EvalConfig
from ragdiff.errors import ConfigError


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    def complete(self, prompt: str, *, model: str) -> str:
        self.calls += 1
        return self.response


QA = json.dumps(
    [
        {"question": "What is the refund window?", "answer": "30 days."},
        {"question": "what is the refund window?", "answer": "duplicate"},
        {"question": "", "answer": "empty question is dropped"},
    ]
)


def test_generate_qa_pairs_parses_and_drops_malformed() -> None:
    pairs = generate_qa_pairs(
        "doc", client=FakeLLM(f"Sure!\n{QA}"), model="m", count=5
    )

    assert pairs[0] == ("What is the refund window?", "30 days.")
    assert all(question for question, _ in pairs)


def test_generate_qa_pairs_tolerates_garbage() -> None:
    assert generate_qa_pairs("doc", client=FakeLLM("no json"), model="m") == []


def test_bootstrap_creates_pending_deduped_synthetic_cases(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("Refunds are accepted within 30 days.")
    config = EvalConfig(
        dataset=tmp_path / "dataset.jsonl", docs=[docs], model="fake-model"
    )

    cases = RagDiff(config, llm_client=FakeLLM(QA)).bootstrap()

    assert [case.question for case in cases] == ["What is the refund window?"]
    assert cases[0].reference == "30 days."
    assert cases[0].source == "synthetic"
    assert cases[0].status == "pending"
    assert read_dataset(config.dataset) == cases


def test_runnable_cases_skips_rejected() -> None:
    cases = [
        DatasetCase(question="keep"),
        DatasetCase(question="drop", status="rejected"),
    ]

    assert [case.question for case in runnable_cases(cases)] == ["keep"]


def test_entrypoint_alias_maps_to_app() -> None:
    assert EvalConfig.model_validate({"entrypoint": "a.b:run"}).app == "a.b:run"
    with pytest.raises(ValueError):
        EvalConfig.model_validate({"entrypoint": "a:x", "app": "b:y"})


def test_unknown_metric_without_implementation_is_a_config_error() -> None:
    with pytest.raises(ConfigError):
        RagDiff(EvalConfig(metrics=["not_a_real_metric"]))


def test_baseline_scores_and_persists(tmp_path, monkeypatch) -> None:
    import sys
    from types import ModuleType

    from ragdiff.storage.filesystem import FileSystemStorage

    app = ModuleType("ragdiff_baseline_app")
    app.run = lambda question, config=None: {"answer": "four"}  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ragdiff_baseline_app", app)

    class Length:
        name = "length"

        def score(self, case, output) -> float:
            return float(len(output.answer))

    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(DatasetCase(question="q").model_dump_json() + "\n")
    config = EvalConfig(
        app="ragdiff_baseline_app:run", dataset=dataset, metrics=["length"]
    )
    storage = FileSystemStorage(tmp_path / "out")

    report = RagDiff(config, metrics=[Length()], storage=storage).baseline()

    assert report.summary["length"]["mean"] == 4.0
    assert (tmp_path / "out" / "runs" / report.run_id / "report.md").is_file()
