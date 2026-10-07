from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

from ragdiff.bootstrap.dataset import DatasetCase
from ragdiff.contract import RunOutput
from ragdiff.metrics.base import Metric
from ragdiff.observability import context
from ragdiff.runner.variants import Variant


@dataclass(slots=True)
class RunRecord:
    question: str
    variant: str
    repeat: int
    answer: str
    contexts: list[str]
    scores: dict[str, float] = field(default_factory=dict)
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def execute(
    cases: list[DatasetCase],
    variants: list[Variant],
    *,
    repeats: int = 1,
    metrics: list[Metric] | None = None,
) -> list[RunRecord]:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    records: list[RunRecord] = []
    for case_index, case in enumerate(cases):
        case_token = context.case_id.set(str(case_index))
        try:
            for variant in variants:
                variant_token = context.variant.set(variant.name)
                try:
                    for repeat in range(repeats):
                        started = time.perf_counter()
                        raw_output = variant.app(case.question, variant.config)
                        output = RunOutput.from_value(raw_output)
                        scores = {
                            metric.name: metric.score(case, output)
                            for metric in metrics or []
                        }
                        records.append(
                            RunRecord(
                                question=case.question,
                                variant=variant.name,
                                repeat=repeat,
                                answer=output.answer,
                                contexts=output.contexts,
                                scores=scores,
                                duration_ms=(time.perf_counter() - started) * 1000,
                                metadata=output.metadata,
                            )
                        )
                finally:
                    context.variant.reset(variant_token)
        finally:
            context.case_id.reset(case_token)
    return records
