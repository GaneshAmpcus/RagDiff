from collections import defaultdict
from statistics import mean
from typing import Any

from ragdiff.compare.stats import paired_interval, summarize
from ragdiff.runner.executor import RunRecord

# A single question counts as regressed when its mean score drops by this much.
REGRESSION_TOLERANCE = 0.05


def compare_records(
    records: list[RunRecord],
    *,
    base: str,
    head: str,
    tolerance: float = REGRESSION_TOLERANCE,
) -> dict[str, dict[str, Any]]:
    """Per-metric base-vs-head comparison, paired by question.

    Repeats are averaged within a question first, so run-to-run judge noise
    shrinks before questions are compared. The confidence interval is over
    per-question deltas.
    """
    grouped: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: {base: [], head: []})
    )
    for record in records:
        if record.variant not in (base, head):
            continue
        for metric, score in record.scores.items():
            grouped[metric][record.question][record.variant].append(score)

    result: dict[str, dict[str, Any]] = {}
    for metric, questions in grouped.items():
        base_scores: list[float] = []
        head_scores: list[float] = []
        deltas: list[float] = []
        per_question: list[dict[str, Any]] = []
        for question, scores in questions.items():
            base_scores.extend(scores[base])
            head_scores.extend(scores[head])
            if not scores[base] or not scores[head]:
                continue
            base_mean, head_mean = mean(scores[base]), mean(scores[head])
            deltas.append(head_mean - base_mean)
            per_question.append(
                {
                    "question": question,
                    "base": base_mean,
                    "head": head_mean,
                    "delta": head_mean - base_mean,
                }
            )
        base_summary = summarize(base_scores)
        head_summary = summarize(head_scores)
        interval = paired_interval(deltas)
        ci_low, ci_high = interval["ci_low"], interval["ci_high"]
        result[metric] = {
            "base": base_summary,
            "head": head_summary,
            "delta": head_summary["mean"] - base_summary["mean"],
            "ci_low": ci_low,
            "ci_high": ci_high,
            "significant": (
                None if ci_low is None else bool(ci_low > 0 or ci_high < 0)
            ),
            "questions": interval["n"],
            "regressed": sorted(
                (item for item in per_question if item["delta"] <= -tolerance),
                key=lambda item: item["delta"],
            ),
            "improved": sum(1 for item in per_question if item["delta"] >= tolerance),
        }
    return result
