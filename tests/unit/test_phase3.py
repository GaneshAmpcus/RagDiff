import sys
from types import ModuleType
from typing import Any

import pytest

from ragdiff import RagDiff
from ragdiff.attribution.engine import attribute, changed_factors
from ragdiff.attribution.suggestions import suggest_fix
from ragdiff.attribution.tier1 import classify_questions, summarize_evidence
from ragdiff.bootstrap.dataset import DatasetCase, write_dataset
from ragdiff.config.schema import EvalConfig, VariantConfig
from ragdiff.runner.executor import RunRecord
from ragdiff.storage.filesystem import FileSystemStorage

DOC = "The refund window is 30 days for all purchases."
TRACKED = {
    "retrieval": ["chunk_size", "top_k"],
    "prompt": ["prompt"],
    "model": ["llm_model"],
}


def demo_app(question: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Tiny RAG app whose three tracked knobs each break answers differently."""
    config = config or {}
    contexts = [DOC[: config.get("chunk_size", 100)]]
    if config.get("prompt", "good") == "bad":
        answer = "Please see our policy page."  # ignores the contexts
    elif config.get("llm_model", "big") == "small":
        answer = "30"  # truncated answer
    elif "30 days" in contexts[0]:
        answer = "30 days"
    else:
        answer = "I don't know."
    return {"answer": answer, "contexts": contexts}


class Quality:
    name = "quality"

    def score(self, case: DatasetCase, output: Any) -> float:
        return 1.0 if "30 days" in output.answer else 0.0


@pytest.fixture
def ragdiff_factory(tmp_path, monkeypatch):
    module = ModuleType("ragdiff_demo_app")
    module.run = demo_app  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ragdiff_demo_app", module)
    monkeypatch.chdir(tmp_path)
    dataset = tmp_path / "dataset.jsonl"
    write_dataset(dataset, [DatasetCase(question=f"q{i}") for i in range(4)])

    def make(head_config: dict[str, Any]) -> RagDiff:
        config = EvalConfig(
            app="ragdiff_demo_app:run",
            dataset=dataset,
            metrics=["quality"],
            thresholds={"quality": -0.1},
            tracked_config=TRACKED,
            variants=[
                VariantConfig(name="base", config={"chunk_size": 100}),
                VariantConfig(name="head", config={"chunk_size": 100, **head_config}),
            ],
        )
        return RagDiff(
            config, metrics=[Quality()], storage=FileSystemStorage(tmp_path / "out")
        )

    return make


def test_retrieval_change_is_attributed_to_retrieval(ragdiff_factory) -> None:
    report = ragdiff_factory({"chunk_size": 10}).compare(base="base", head="head")

    assert report.verdict == "fail"
    assert report.culprit == "retrieval"
    assert report.attribution is not None
    assert report.attribution.tier == 1
    assert "chunk_size" in report.attribution.suggestion


def test_prompt_change_is_attributed_to_prompt(ragdiff_factory) -> None:
    report = ragdiff_factory({"prompt": "bad"}).compare(base="base", head="head")

    assert report.culprit == "prompt"
    assert report.attribution is not None and report.attribution.tier == 1


def test_model_change_is_attributed_to_model(ragdiff_factory) -> None:
    report = ragdiff_factory({"llm_model": "small"}).compare(base="base", head="head")

    assert report.culprit == "model"


def test_prompt_and_model_changed_uses_ablation(ragdiff_factory, tmp_path) -> None:
    # The model swap is harmless ("medium" behaves like "big"); the prompt breaks it.
    report = ragdiff_factory({"prompt": "bad", "llm_model": "medium"}).compare(
        base="base", head="head"
    )

    assert report.culprit == "prompt"
    assert report.attribution is not None
    assert report.attribution.tier == 2
    assert report.attribution.evidence["recovery"]["prompt"] > 0
    assert report.attribution.evidence["recovery"]["model"] == 0
    run_dir = tmp_path / "out" / "runs" / report.run_id
    assert "Attribution" in (run_dir / "report.md").read_text(encoding="utf-8")


def test_harmless_change_has_no_attribution(ragdiff_factory) -> None:
    report = ragdiff_factory({"llm_model": "medium"}).compare(base="base", head="head")

    assert report.verdict == "pass"
    assert report.attribution is None


def _record(question: str, variant: str, contexts: list[str]) -> RunRecord:
    return RunRecord(
        question=question, variant=variant, repeat=0, answer="a", contexts=contexts
    )


def test_tier1_flags_changed_contexts_and_lost_chunks() -> None:
    records = [
        _record("q1", "base", ["policy chunk", "header"]),
        _record("q1", "head", ["header"]),
        _record("q2", "base", ["same"]),
        _record("q2", "head", ["same"]),
    ]

    evidence = classify_questions(records, ["q1", "q2"], base="base", head="head")

    assert [item.changed for item in evidence] == [True, False]
    assert evidence[0].lost == ["policy chunk"]
    assert summarize_evidence(evidence)["share_retrieval"] == 0.5


def test_changed_factors_and_unknown_config_paths() -> None:
    assert changed_factors(TRACKED, {"top_k": 3}, {"top_k": 6, "prompt": "x"}) == [
        "retrieval",
        "prompt",
    ]
    assert changed_factors({}, {"a": 1}, {"a": 2}) == []


def test_attribute_returns_none_without_a_breach() -> None:
    diffs = {"m": {"delta": 0.0, "regressed": [], "ci_high": None}}

    assert (
        attribute(
            records=[], differences=diffs, thresholds={"m": -0.1}, base="b", head="h"
        )
        is None
    )


def test_suggest_fix_names_the_changed_values() -> None:
    text = suggest_fix(
        "retrieval",
        tracked=TRACKED,
        base_config={"chunk_size": 800},
        head_config={"chunk_size": 400},
    )

    assert "`chunk_size` (800 -> 400)" in text


def test_tracked_config_validation() -> None:
    config = EvalConfig.model_validate({"tracked_config": {"prompt": "prompts/s.txt"}})
    assert config.tracked_config == {"prompt": ["prompts/s.txt"]}
    with pytest.raises(ValueError):
        EvalConfig.model_validate({"tracked_config": {"database": ["x"]}})
