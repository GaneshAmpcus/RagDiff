from ragdiff.bootstrap.dataset import DatasetCase, read_dataset, write_dataset
from ragdiff.compare.stats import summarize
from ragdiff.contract import RunOutput
from ragdiff.llm.cache import CachedLLMClient, DiskCache
from ragdiff.observability.redaction import redact


def test_run_output_accepts_mapping() -> None:
    output = RunOutput.from_value({"answer": "hello", "contexts": ["source"]})

    assert output.answer == "hello"
    assert output.contexts == ["source"]


def test_dataset_round_trip(tmp_path) -> None:
    path = tmp_path / "dataset.jsonl"
    write_dataset(path, [DatasetCase(question="What is RagDiff?")])

    assert read_dataset(path) == [DatasetCase(question="What is RagDiff?")]


def test_summarize_and_redact() -> None:
    assert summarize([1.0, 3.0])["mean"] == 2.0
    assert "secret=[REDACTED]" in redact("secret=abc123")


def test_cached_llm_client_uses_disk_cache(tmp_path) -> None:
    class FakeClient:
        calls = 0

        def complete(self, prompt: str, *, model: str) -> str:
            self.calls += 1
            return "response"

    client = FakeClient()
    cached = CachedLLMClient(client, DiskCache(tmp_path))

    assert cached.complete("prompt", model="model") == "response"
    assert cached.complete("prompt", model="model") == "response"
    assert client.calls == 1
