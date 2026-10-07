from collections import defaultdict
from typing import Any

from ragdiff.compare.stats import summarize
from ragdiff.runner.executor import RunRecord


def compare_records(
    records: list[RunRecord], *, base: str, head: str
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {base: [], head: []}
    )
    for record in records:
        if record.variant not in (base, head):
            continue
        for metric, score in record.scores.items():
            grouped[metric][record.variant].append(score)
    result: dict[str, dict[str, Any]] = {}
    for metric, values in grouped.items():
        base_summary = summarize(values[base])
        head_summary = summarize(values[head])
        result[metric] = {
            "base": base_summary,
            "head": head_summary,
            "delta": head_summary["mean"] - base_summary["mean"],
        }
    return result
