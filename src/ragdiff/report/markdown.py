from typing import Any

MAX_LISTED_QUESTIONS = 5


def _interval(result: dict[str, Any]) -> str:
    low, high = result.get("ci_low"), result.get("ci_high")
    if low is None or high is None:
        return "n/a"
    return f"[{low:+.4f}, {high:+.4f}]"


def _attribution_lines(attribution: dict[str, Any]) -> list[str]:
    evidence = attribution.get("evidence", {})
    lines = [
        "",
        "## Attribution",
        "",
        (
            f"**Culprit:** {attribution['factor']} (tier {attribution['tier']}, "
            f"confidence {attribution['confidence']:.2f})"
        ),
        "",
        f"**Suggested fix:** {attribution['suggestion']}",
    ]
    tier1 = evidence.get("tier1")
    if tier1:
        lines.extend(
            [
                "",
                (
                    f"- {tier1['contexts_changed']} of {tier1['questions']} regressed "
                    "question(s) retrieved different contexts"
                ),
            ]
        )
    for factor, value in evidence.get("recovery", {}).items():
        lines.append(f"- Reverting `{factor}` recovers {value:+.3f} on regressed questions")
    for item in evidence.get("examples", []):
        lost = f" lost: {item['lost'][0]!r}" if item.get("lost") else ""
        lines.append(f"- {item['question']}{lost}")
    return lines


def render_markdown(
    differences: dict[str, dict[str, Any]],
    *,
    verdict: str,
    attribution: dict[str, Any] | None = None,
) -> str:
    lines = ["# RagDiff report", "", f"**Verdict:** {verdict}", ""]
    if attribution:
        lines.extend(_attribution_lines(attribution)[1:] + [""])
    if differences:
        lines.extend(
            [
                "| Metric | Base mean | Head mean | Delta | 95% CI | Regressed |",
                "| --- | ---: | ---: | ---: | --- | ---: |",
            ]
        )
        for metric, result in differences.items():
            regressed = len(result.get("regressed", []))
            lines.append(
                f"| {metric} | {result['base']['mean']:.4f} | "
                f"{result['head']['mean']:.4f} | {result['delta']:+.4f} | "
                f"{_interval(result)} | {regressed} |"
            )
        for metric, result in differences.items():
            regressed_items = result.get("regressed", [])
            if not regressed_items:
                continue
            lines.extend(["", f"## Regressed questions: {metric}", ""])
            for item in regressed_items[:MAX_LISTED_QUESTIONS]:
                lines.append(
                    f"- {item['question']} ({item['base']:.3f} -> "
                    f"{item['head']:.3f}, {item['delta']:+.3f})"
                )
            hidden = len(regressed_items) - MAX_LISTED_QUESTIONS
            if hidden > 0:
                lines.append(f"- ... and {hidden} more")
    else:
        lines.append("No metric results were available.")
    return "\n".join(lines) + "\n"


def render_baseline_markdown(summary: dict[str, dict[str, Any]], *, cases: int) -> str:
    lines = ["# RagDiff baseline", "", f"Scored {cases} case(s).", ""]
    if summary:
        lines.extend(
            ["| Metric | Mean | Spread | Samples |", "| --- | ---: | ---: | ---: |"]
        )
        for metric, stats in sorted(summary.items()):
            lines.append(
                f"| {metric} | {stats['mean']:.4f} | "
                f"{stats['spread']:.4f} | {stats['count']} |"
            )
    else:
        lines.append("No metrics were configured, so nothing was scored.")
    return "\n".join(lines) + "\n"
