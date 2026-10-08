from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ragdiff.attribution.engine import Ablator, Attribution, attribute
from ragdiff.attribution.suggestions import suggest_causes
from ragdiff.bootstrap.dataset import (
    DatasetCase,
    read_dataset,
    runnable_cases,
    write_dataset,
)
from ragdiff.bootstrap.generator import generate_qa_pairs
from ragdiff.bootstrap.ingest import read_documents, split_text
from ragdiff.compare.diff import compare_records
from ragdiff.compare.stats import summarize
from ragdiff.compare.verdict import evaluate_verdict
from ragdiff.config.loader import load_config
from ragdiff.config.schema import EvalConfig
from ragdiff.contract import load_app
from ragdiff.errors import ConfigError
from ragdiff.llm.base import LLMClient
from ragdiff.llm.cache import Cache, CachedLLMClient, DiskCache
from ragdiff.metrics.base import Metric
from ragdiff.metrics.builtin import build_builtin_metrics
from ragdiff.metrics.registry import MetricRegistry
from ragdiff.observability import context
from ragdiff.report.markdown import render_baseline_markdown, render_markdown
from ragdiff.runner.executor import RunRecord, execute, score_records
from ragdiff.runner.subprocess_runner import run_ref
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
    attribution: Attribution | None = None


@dataclass(slots=True)
class BaselineReport:
    run_id: str
    cases: int
    summary: dict[str, dict[str, Any]]
    records: list[RunRecord]


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
        missing = sorted(set(config.metrics) - {metric.name for metric in (metrics or [])})
        if missing:
            # Fall back to the built-in metrics; raises ConfigError for
            # names with no built-in implementation.
            for metric in build_builtin_metrics(
                missing, judge_model=config.judge_model
            ):
                registry.register(metric)
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
            seen: set[str] = set()
            for path, text in read_documents(self.config.docs):
                chunks = split_text(
                    text,
                    chunk_size=self.config.chunk_size,
                    overlap=self.config.chunk_overlap,
                )
                for chunk_index, chunk in enumerate(chunks):
                    pairs = generate_qa_pairs(
                        chunk,
                        client=self.llm_client,
                        model=self.config.model,
                        count=questions_per_document,
                    )
                    for question, answer in pairs:
                        key = question.casefold()
                        if key in seen:
                            continue
                        seen.add(key)
                        cases.append(
                            DatasetCase(
                                question=question,
                                reference=answer,
                                source="synthetic",
                                status="pending",
                                metadata={
                                    "document": str(path),
                                    "chunk": chunk_index,
                                },
                            )
                        )
        write_dataset(self.config.dataset, cases)
        return cases

    def baseline(self) -> BaselineReport:
        """Zero-to-scored-baseline: ensure a dataset exists, run the app, score it."""
        if self.config.app is None:
            raise ConfigError("Config must define an 'app' entrypoint")
        cases = runnable_cases(self.bootstrap())
        if not cases:
            raise ConfigError("The dataset has no runnable cases")
        records = execute(
            cases,
            [Variant(name="baseline", app=load_app(self.config.app))],
            repeats=self.config.repeats,
            metrics=self.metrics,
        )
        scores: dict[str, list[float]] = {}
        for record in records:
            for metric, score in record.scores.items():
                scores.setdefault(metric, []).append(score)
        summary = {metric: summarize(values) for metric, values in scores.items()}
        run_id = uuid.uuid4().hex
        token = context.run_id.set(run_id)
        try:
            run_path = Path("runs") / run_id
            self.storage.write_jsonl(
                run_path / "results.jsonl", [record.to_dict() for record in records]
            )
            self.storage.write_json(
                run_path / "meta.json",
                {
                    "run_id": run_id,
                    "kind": "baseline",
                    "summary": summary,
                    "config": self.config.model_dump(mode="json"),
                },
            )
            self.storage.write_text(
                run_path / "report.md",
                render_baseline_markdown(summary, cases=len(cases)),
            )
        finally:
            context.run_id.reset(token)
        return BaselineReport(
            run_id=run_id, cases=len(cases), summary=summary, records=records
        )

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

        cases = runnable_cases(read_dataset(self.config.dataset))
        records = execute(
            cases,
            runnable,
            repeats=self.config.repeats,
            metrics=self.metrics,
        )
        return self._finalize(
            records,
            base=base,
            head=head,
            base_config=variants[base].config,
            head_config=variants[head].config,
            ablate=self._make_ablator(cases, runnable[1], variants[base].config),
        )

    def _make_ablator(
        self,
        cases: list[DatasetCase],
        head: Variant,
        base_config: dict[str, Any],
    ) -> Ablator:
        """Re-run head with one factor's tracked keys reverted to base values."""
        by_question = {case.question: case for case in cases}
        by_name = {metric.name: metric for metric in self.metrics}

        def ablate(factor: str, questions: list[str], metric: str) -> float:
            config = dict(head.config)
            for key in self.config.tracked_config.get(factor, []):
                if key in base_config:
                    config[key] = base_config[key]
                else:
                    config.pop(key, None)
            records = execute(
                [by_question[question] for question in questions],
                [Variant(name=f"ablation:{factor}", app=head.app, config=config)],
                repeats=self.config.repeats,
                metrics=[by_name[metric]],
            )
            scores = [record.scores[metric] for record in records]
            return sum(scores) / len(scores)

        return ablate

    def compare_refs(
        self,
        *,
        base_ref: str,
        head_ref: str,
        repository: str | Path = ".",
    ) -> CompareReport:
        """Compare the app at two git revisions, each run in its own worktree."""
        if self.config.app is None:
            raise ConfigError("Config must define an 'app' entrypoint")
        if base_ref == head_ref:
            raise ConfigError("Base and head revisions must be different")
        cases = runnable_cases(read_dataset(self.config.dataset))
        if not cases:
            raise ConfigError("The dataset has no runnable cases")
        records: list[RunRecord] = []
        for name, revision in (("base", base_ref), ("head", head_ref)):
            records.extend(
                run_ref(
                    repository=repository,
                    revision=revision,
                    entrypoint=self.config.app,
                    cases=cases,
                    variant=name,
                    repeats=self.config.repeats,
                    app_dir=self.config.app_dir,
                )
            )
        score_records(records, cases, self.metrics)
        return self._finalize(
            records,
            base="base",
            head="head",
            extra={"base_ref": base_ref, "head_ref": head_ref},
        )

    def _finalize(
        self,
        records: list[RunRecord],
        *,
        base: str,
        head: str,
        extra: dict[str, Any] | None = None,
        base_config: dict[str, Any] | None = None,
        head_config: dict[str, Any] | None = None,
        ablate: Ablator | None = None,
    ) -> CompareReport:
        differences = compare_records(records, base=base, head=head)
        verdict = (
            evaluate_verdict(differences, self.config.thresholds)
            if differences
            else "inconclusive"
        )
        attribution = (
            attribute(
                records=records,
                differences=differences,
                thresholds=self.config.thresholds,
                base=base,
                head=head,
                tracked=self.config.tracked_config,
                base_config=base_config,
                head_config=head_config,
                ablate=ablate,
            )
            if verdict == "fail"
            else None
        )
        culprit = attribution.factor if attribution else None

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
                    **(extra or {}),
                    "config": self.config.model_dump(mode="json"),
                },
            )
            self.storage.write_text(
                Path("runs") / run_id / "report.md",
                render_markdown(
                    differences,
                    verdict=verdict,
                    attribution=attribution.to_dict() if attribution else None,
                ),
            )
            self.storage.write_json(
                Path("runs") / run_id / "attribution.json",
                {
                    "culprit": culprit,
                    "attribution": attribution.to_dict() if attribution else None,
                    "suggestions": suggest_causes(differences),
                },
            )
        finally:
            context.run_id.reset(token)
        return CompareReport(
            run_id=run_id,
            verdict=verdict,
            differences=differences,
            records=records,
            culprit=culprit,
            attribution=attribution,
        )
