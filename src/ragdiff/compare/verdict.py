from typing import Any


def evaluate_verdict(
    differences: dict[str, dict[str, Any]],
    thresholds: dict[str, float],
) -> str:
    """``pass``, ``fail`` or ``inconclusive``.

    A metric fails only when its delta is below the threshold *and* the change is
    distinguishable from noise (the 95% interval lies entirely below zero). A
    breach inside the noise band is ``inconclusive``. With too few questions to
    compute an interval, the point estimate decides.
    """
    if not differences:
        return "inconclusive"
    noisy_breach = False
    for metric, minimum_delta in thresholds.items():
        if metric not in differences:
            return "inconclusive"
        entry = differences[metric]
        if entry["delta"] >= minimum_delta:
            continue
        ci_high = entry.get("ci_high")
        if ci_high is None or ci_high < 0:
            return "fail"
        noisy_breach = True
    return "inconclusive" if noisy_breach else "pass"
