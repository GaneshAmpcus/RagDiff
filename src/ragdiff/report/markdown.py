from typing import Any


def render_markdown(
    differences: dict[str, dict[str, Any]], *, verdict: str
) -> str:
    lines = ["# RagDiff report", "", f"**Verdict:** {verdict}", ""]
    if differences:
        lines.extend(
            [
                "| Metric | Base mean | Head mean | Delta |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for metric, result in differences.items():
            lines.append(
                f"| {metric} | {result['base']['mean']:.4f} | "
                f"{result['head']['mean']:.4f} | {result['delta']:+.4f} |"
            )
    else:
        lines.append("No metric results were available.")
    return "\n".join(lines) + "\n"
