import subprocess
from pathlib import Path

import pytest

from ragdiff import RagDiff
from ragdiff.bootstrap.dataset import DatasetCase, write_dataset
from ragdiff.compare.diff import compare_records
from ragdiff.compare.stats import paired_interval, t_critical
from ragdiff.compare.verdict import evaluate_verdict
from ragdiff.config.schema import EvalConfig
from ragdiff.runner.executor import RunRecord
from ragdiff.storage.filesystem import FileSystemStorage


def _record(question: str, variant: str, score: float, repeat: int = 0) -> RunRecord:
    return RunRecord(
        question=question,
        variant=variant,
        repeat=repeat,
        answer="a",
        contexts=[],
        scores={"m": score},
    )


def _records(base: list[float], head: list[float]) -> list[RunRecord]:
    records = []
    for index, (b, h) in enumerate(zip(base, head)):
        records.append(_record(f"q{index}", "base", b))
        records.append(_record(f"q{index}", "head", h))
    return records


def test_t_critical_and_interval() -> None:
    assert t_critical(1) == pytest.approx(12.706)
    assert paired_interval([1.0])["ci_low"] is None
    interval = paired_interval([-0.1, -0.1, -0.1])
    assert interval["ci_high"] == pytest.approx(-0.1)


def test_consistent_drop_is_significant_and_fails() -> None:
    diffs = compare_records(
        _records([0.9, 0.9, 0.8, 0.9], [0.7, 0.8, 0.6, 0.7]), base="base", head="head"
    )

    assert diffs["m"]["significant"] is True
    assert len(diffs["m"]["regressed"]) == 4
    assert evaluate_verdict(diffs, {"m": -0.03}) == "fail"


def test_noisy_drop_is_inconclusive_not_fail() -> None:
    diffs = compare_records(
        _records([0.9, 0.5, 0.9, 0.5], [0.4, 0.9, 0.4, 0.8]), base="base", head="head"
    )

    assert diffs["m"]["delta"] < -0.03
    assert diffs["m"]["significant"] is False
    assert evaluate_verdict(diffs, {"m": -0.03}) == "inconclusive"


def test_harmless_change_passes() -> None:
    diffs = compare_records(
        _records([0.8, 0.8, 0.8], [0.8, 0.8, 0.8]), base="base", head="head"
    )

    assert evaluate_verdict(diffs, {"m": -0.03}) == "pass"
    assert diffs["m"]["regressed"] == []


def test_repeats_are_averaged_within_question() -> None:
    records = [
        _record("q", "base", 1.0, 0),
        _record("q", "base", 0.0, 1),
        _record("q", "head", 0.5, 0),
        _record("q", "head", 0.5, 1),
    ]

    diffs = compare_records(records, base="base", head="head")

    assert diffs["m"]["questions"] == 1
    assert diffs["m"]["regressed"] == []


def test_single_question_falls_back_to_point_estimate() -> None:
    diffs = compare_records(_records([0.9], [0.5]), base="base", head="head")

    assert diffs["m"]["ci_high"] is None
    assert evaluate_verdict(diffs, {"m": -0.03}) == "fail"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


class AnswerLength:
    name = "answer_length"

    def score(self, case, output) -> float:  # type: ignore[no-untyped-def]
        return float(len(output.answer))


def test_compare_refs_runs_each_revision_in_isolation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "demo_app.py").write_text(
        "def run(question, config=None):\n    return {'answer': 'long answer here'}\n"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    base_sha = _git(repo, "rev-parse", "HEAD")
    (repo / "demo_app.py").write_text(
        "def run(question, config=None):\n    return {'answer': 'x'}\n"
    )
    _git(repo, "commit", "-q", "-am", "head")
    head_sha = _git(repo, "rev-parse", "HEAD")

    dataset = tmp_path / "dataset.jsonl"
    write_dataset(
        dataset, [DatasetCase(question="q1"), DatasetCase(question="q2")]
    )
    config = EvalConfig(
        app="demo_app:run",
        dataset=dataset,
        metrics=["answer_length"],
        thresholds={"answer_length": -1.0},
    )

    report = RagDiff(
        config,
        metrics=[AnswerLength()],
        storage=FileSystemStorage(tmp_path / "out"),
    ).compare_refs(base_ref=base_sha, head_ref=head_sha, repository=repo)

    assert report.verdict == "fail"
    assert report.differences["answer_length"]["delta"] < 0
    assert len(report.records) == 4
