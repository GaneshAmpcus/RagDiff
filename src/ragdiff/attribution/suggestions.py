from typing import Any


def suggest_causes(
    differences: dict[str, dict[str, Any]],
) -> list[str]:
    return [
        f"{metric} changed by {value['delta']:+.3f} between the compared variants."
        for metric, value in differences.items()
        if value["delta"] != 0
    ]


def describe_changes(
    keys: list[str], base_config: dict[str, Any], head_config: dict[str, Any]
) -> str:
    parts = []
    for key in keys:
        before, after = base_config.get(key), head_config.get(key)
        if before != after:
            parts.append(f"`{key}` ({before!r} -> {after!r})")
    return ", ".join(parts)


def suggest_fix(
    factor: str,
    *,
    tracked: dict[str, list[str]],
    base_config: dict[str, Any],
    head_config: dict[str, Any],
) -> str:
    """One-line suggested fix for a culprit type."""
    changes = describe_changes(tracked.get(factor, []), base_config, head_config)
    if factor == "retrieval":
        target = changes or "the retrieval settings"
        return (
            f"Revert {target}, or raise `top_k` so the chunk holding the answer "
            "is still retrieved."
        )
    if factor == "prompt":
        target = changes or "the prompt change"
        return (
            f"Revert {target}, or restore the instruction that grounds answers "
            "in the retrieved context."
        )
    if factor == "model":
        target = changes or "the model change"
        return f"Revert {target}, or re-tune the prompt for the new model."
    if factor == "generation":
        return (
            "Retrieved contexts are unchanged but answers got worse: revert the "
            "prompt or model change."
        )
    if factor == "multiple":
        return (
            "Several changes contribute; revert them one at a time and re-run "
            "to isolate each."
        )
    return "Inspect the regressed questions listed in the report."
