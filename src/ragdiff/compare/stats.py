from math import sqrt
from statistics import mean, stdev


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
