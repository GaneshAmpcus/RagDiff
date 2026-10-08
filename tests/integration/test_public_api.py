import sys
from types import ModuleType

from ragdiff import RagDiff
from ragdiff.bootstrap.dataset import DatasetCase, write_dataset
from ragdiff.config.schema import EvalConfig, VariantConfig
from ragdiff.storage.filesystem import FileSystemStorage


class AnswerLength:
    name = "answer_length"

    def score(self, case, output) -> float:
        return float(len(output.answer))


def test_public_api_compares_and_persists_variants(tmp_path, monkeypatch) -> None:
    fake_app = ModuleType("ragdiff_test_app")

    def answer(question: str, config: dict) -> dict[str, str]:
        return {"answer": config["answer"]}

    fake_app.answer = answer
    monkeypatch.setitem(sys.modules, "ragdiff_test_app", fake_app)
    monkeypatch.chdir(tmp_path)

    dataset = tmp_path / "dataset.jsonl"
    write_dataset(dataset, [DatasetCase(question="question")])
    config = EvalConfig(
        dataset=dataset,
        metrics=["answer_length"],
        thresholds={"answer_length": 0},
        variants=[
            VariantConfig(
                name="baseline",
                app="ragdiff_test_app:answer",
                config={"answer": "short"},
            ),
            VariantConfig(
                name="candidate",
                app="ragdiff_test_app:answer",
                config={"answer": "longer"},
            ),
        ],
    )
    storage = FileSystemStorage(tmp_path / "custom-artifacts")
    ragdiff = RagDiff(config, metrics=[AnswerLength()], storage=storage)

    report = ragdiff.compare(base="baseline", head="candidate")

    assert report.verdict == "pass"
    assert report.culprit is None  # attribution only runs on a failed gate
    run_dir = tmp_path / "custom-artifacts" / "runs" / report.run_id
    assert (run_dir / "results.jsonl").is_file()
    assert (run_dir / "meta.json").is_file()
    assert (run_dir / "attribution.json").is_file()
    assert (run_dir / "report.md").is_file()
