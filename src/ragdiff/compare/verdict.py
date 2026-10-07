from typing import Any


def evaluate_verdict(
    differences: dict[str, dict[str, Any]],
    thresholds: dict[str, float],
) -> str:
    if not differences:
        return "inconclusive"
    for metric, minimum_delta in thresholds.items():
        if metric not in differences:
            return "inconclusive"
        if differences[metric]["delta"] < minimum_delta:
            return "fail"
    return "pass"
