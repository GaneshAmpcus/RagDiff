from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ragdiff.attribution.suggestions import suggest_causes
from ragdiff.bootstrap.dataset import DatasetCase, read_dataset, write_dataset
from ragdiff.bootstrap.generator import generate_questions
from ragdiff.bootstrap.ingest import read_documents, split_text
from ragdiff.compare.diff import compare_records
from ragdiff.compare.verdict import evaluate_verdict
from ragdiff.config.loader import load_config
from ragdiff.config.schema import EvalConfig
from ragdiff.contract import load_app
from ragdiff.errors import ConfigError
from ragdiff.llm.base import LLMClient
from ragdiff.llm.cache import Cache, CachedLLMClient, DiskCache
from ragdiff.metrics.base import Metric
from ragdiff.metrics.registry import MetricRegistry
from ragdiff.observability import context
from ragdiff.report.markdown import render_markdown
from ragdiff.runner.executor import RunRecord, execute
from ragdiff.runner.variants import Variant
from ragdiff.storage.base import Storage
from ragdiff.storage.filesystem import FileSystemStorage


@dataclass(slots=True)
class CompareReport:
    run_id: str
    verdict: str
    differences: dict[str, dict[str, Any]]
    records: list[RunRecord]
    culprit: str | None


class RagDiff:
    """Library entrypoint for bootstrapping data and comparing configured variants."""

    def __init__(
        self,
        config: EvalConfig,
        *,
        llm_client: LLMClient | None = None,
        cache: Cache | None = None,
        metrics: list[Metric] | None = None,
        storage: Storage | None = None,
    ) -> None:
        self.config = config
        self.llm_client = (
            CachedLLMClient(
                llm_client, cache if cache is not None else DiskCache()
            )
            if llm_client is not None
            else None
        )
        self.storage = storage or FileSystemStorage()
        registry = MetricRegistry()
        for metric in metrics or []:
            registry.register(metric)
        missing = set(config.metrics) - {metric.name for metric in (metrics or [])}
        if missing:
            names = ", ".join(sorted(missing))
            raise ConfigError(f"No implementation was provided for metric(s): {names}")
        self.metrics = [registry.get(name) for name in config.metrics]

    @classmethod
    def from_config(
        cls,
        path: str | Path,
        *,
        llm_client: LLMClient | None = None,
        cache: Cache | None = None,
        metrics: list[Metric] | None = None,
        storage: Storage | None = None,
    ) -> RagDiff:
        return cls(
            load_config(path),
            llm_client=llm_client,
            cache=cache,
            metrics=metrics,
            storage=storage,
        )

    def bootstrap(self, *, questions_per_document: int = 3) -> list[DatasetCase]:
        if self.config.dataset.exists():
            return read_dataset(self.config.dataset)
        cases: list[DatasetCase] = []
        if self.config.docs:
            if self.llm_client is None or self.config.model is None:
                raise ConfigError(
                    "Generating a dataset from docs requires an LLM client and "
                    "a configured model"
                )
            for path, text in read_documents(self.config.docs):
                chunks = split_text(
                    text,
                    chunk_size=self.config.chunk_size,
                    overlap=self.config.chunk_overlap,
                )
                for chunk_index, chunk in enumerate(chunks):
                    questions = generate_questions(
                        chunk,
                        client=self.llm_client,
                        model=self.config.model,
                        count=questions_per_document,
                    )
                    cases.extend(
                        DatasetCase(
                            question=question,
                            metadata={"source": str(path), "chunk": chunk_index},
                        )
                        for question in questions
                    )
        write_dataset(self.config.dataset, cases)
        return cases

    def compare(self, *, base: str, head: str) -> CompareReport:
        variants = {variant.name: variant for variant in self.config.variants}
        unknown = {base, head} - variants.keys()
        if unknown:
            raise ConfigError(
                "Unknown variant name(s): " + ", ".join(sorted(unknown))
            )
        if base == head:
            raise ConfigError("Base and head variants must be different")
        configured = [variants[base], variants[head]]
        runnable: list[Variant] = []
        for variant in configured:
            entrypoint = variant.app or self.config.app
            if entrypoint is None:
                raise ConfigError(
                    f"Variant {variant.name!r} and the top-level config must "
                    "define an app entrypoint"
                )
            runnable.append(
                Variant(
                    name=variant.name,
                    app=load_app(entrypoint),
                    config=variant.config,
                )
            )

        records = execute(
            read_dataset(self.config.dataset),
            runnable,
            repeats=self.config.repeats,
            metrics=self.metrics,
        )
        differences = compare_records(records, base=base, head=head)
        verdict = (
            evaluate_verdict(differences, self.config.thresholds)
            if differences
            else "inconclusive"
        )
        culprit = None
        if differences:
            culprit = min(
                differences,
                key=lambda metric: differences[metric]["delta"],
            )

        run_id = uuid.uuid4().hex
        token = context.run_id.set(run_id)
        try:
            self.storage.write_jsonl(
                Path("runs") / run_id / "results.jsonl",
                [record.to_dict() for record in records],
            )
            self.storage.write_json(
                Path("runs") / run_id / "meta.json",
                {
                    "run_id": run_id,
                    "base": base,
                    "head": head,
                    "verdict": verdict,
                    "config": self.config.model_dump(mode="json"),
                },
            )
            self.storage.write_text(
                Path("runs") / run_id / "report.md",
                render_markdown(differences, verdict=verdict),
            )
            self.storage.write_json(
                Path("runs") / run_id / "attribution.json",
                {"culprit": culprit, "suggestions": suggest_causes(differences)},
            )
        finally:
            context.run_id.reset(token)
        return CompareReport(
            run_id=run_id,
            verdict=verdict,
            differences=differences,
            records=records,
            culprit=culprit,
        )
