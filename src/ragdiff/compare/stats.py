from math import sqrt
from statistics import mean, stdev
from typing import Any

# Two-sided 95% Student-t critical values by degrees of freedom.
_T95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
    8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
    15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056,
    27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}  # fmt: skip


def summarize(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "mean": 0.0, "spread": 0.0}
    return {
        "count": len(values),
        "mean": mean(values),
        "spread": stdev(values) if len(values) > 1 else 0.0,
    }


def standard_error(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return stdev(values) / sqrt(len(values))


def t_critical(degrees_of_freedom: int) -> float:
    if degrees_of_freedom < 1:
        raise ValueError("degrees_of_freedom must be positive")
    if degrees_of_freedom in _T95:
        return _T95[degrees_of_freedom]
    return 2.0 if degrees_of_freedom <= 120 else 1.96


def paired_interval(deltas: list[float]) -> dict[str, Any]:
    """Mean of per-question deltas with a 95% confidence interval.

    With fewer than two questions no interval can be computed, so ``ci_low`` and
    ``ci_high`` are ``None`` and callers must fall back to the point estimate.
    """
    count = len(deltas)
    average = mean(deltas) if deltas else 0.0
    if count < 2:
        return {"n": count, "mean": average, "ci_low": None, "ci_high": None}
    half_width = t_critical(count - 1) * standard_error(deltas)
    return {
        "n": count,
        "mean": average,
        "ci_low": average - half_width,
        "ci_high": average + half_width,
    }
