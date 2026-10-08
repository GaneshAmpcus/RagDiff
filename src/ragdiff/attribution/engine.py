"""Decide which change caused a regression: retrieval, prompt, or model."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from statistics import mean
from typing import Any

from ragdiff.attribution.suggestions import suggest_fix
from ragdiff.attribution.tier1 import classify_questions, summarize_evidence
from ragdiff.runner.executor import RunRecord

# Share of regressed questions whose retrieved contexts changed.
RETRIEVAL_SHARE = 0.7
GENERATION_SHARE = 0.3
# A factor is the culprit if reverting it recovers at least this share of the drop.
RECOVERY_SHARE = 0.5
FACTOR_ORDER = ("retrieval", "prompt", "model")
MAX_EXAMPLES = 3
EXAMPLE_LENGTH = 160

# (factor, regressed questions, metric) -> mean head score with that factor
# reverted to its base value, run on the regressed questions only.
Ablator = Callable[[str, list[str], str], float]


@dataclass(slots=True)
class Attribution:
    tier: int
    factor: str
    confidence: float
    suggestion: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def changed_factors(
    tracked: dict[str, list[str]],
    base_config: dict[str, Any],
    head_config: dict[str, Any],
) -> list[str]:
    return [
        factor
        for factor in FACTOR_ORDER
        if any(
            base_config.get(key) != head_config.get(key)
            for key in tracked.get(factor, [])
        )
    ]


def attribute(
    *,
    records: list[RunRecord],
    differences: dict[str, dict[str, Any]],
    thresholds: dict[str, float],
    base: str,
    head: str,
    tracked: dict[str, list[str]] | None = None,
    base_config: dict[str, Any] | None = None,
    head_config: dict[str, Any] | None = None,
    ablate: Ablator | None = None,
) -> Attribution | None:
    """Attribute a regression. Returns ``None`` when no metric breached."""
    tracked = tracked or {}
    base_config = base_config or {}
    head_config = head_config or {}
    failing = [
        metric
        for metric, minimum in thresholds.items()
        if metric in differences and differences[metric]["delta"] < minimum
    ]
    if not failing:
        return None
    target = min(failing, key=lambda metric: differences[metric]["delta"])
    questions = list(
        dict.fromkeys(
            item["question"]
            for metric in failing
            for item in differences[metric]["regressed"]
        )
    )
    changed = changed_factors(tracked, base_config, head_config)

    def build(
        tier: int, factor: str, confidence: float, extra: dict[str, Any] | None = None
    ) -> Attribution:
        return Attribution(
            tier=tier,
            factor=factor,
            confidence=round(max(0.0, min(1.0, confidence)), 3),
            suggestion=suggest_fix(
                factor, tracked=tracked, base_config=base_config, head_config=head_config
            ),
            evidence={
                "target_metric": target,
                "regressed_questions": len(questions),
                "changed_factors": changed,
                **(extra or {}),
            },
        )

    if not questions:
        return build(1, "unknown", 0.0)

    evidence = classify_questions(records, questions, base=base, head=head)
    summary = summarize_evidence(evidence)
    share = summary["share_retrieval"]
    examples = [
        {
            "question": item.question,
            "lost": [text[:EXAMPLE_LENGTH] for text in item.lost[:2]],
        }
        for item in evidence
        if item.changed
    ][:MAX_EXAMPLES]
    tier1 = {"tier1": summary, "examples": examples}
    generation = [factor for factor in changed if factor in ("prompt", "model")]

    if share >= RETRIEVAL_SHARE and (not changed or "retrieval" in changed):
        return build(1, "retrieval", share, tier1)
    if share <= GENERATION_SHARE and (not changed or generation):
        if len(generation) > 1:
            return _tier2(build, generation, ablate, differences[target], questions, target, tier1)
        return build(1, generation[0] if generation else "generation", 1 - share, tier1)
    if len(changed) == 1:
        return build(1, changed[0], 1.0, {**tier1, "note": "only tracked change"})
    if len(changed) > 1:
        return _tier2(build, changed, ablate, differences[target], questions, target, tier1)
    factor = "retrieval" if share >= 0.5 else "generation"
    return build(1, factor, abs(share - 0.5) * 2, {**tier1, "note": "mixed signals"})


def _tier2(
    build: Callable[..., Attribution],
    candidates: list[str],
    ablate: Ablator | None,
    difference: dict[str, Any],
    questions: list[str],
    target: str,
    tier1: dict[str, Any],
) -> Attribution:
    """Revert one candidate factor at a time and see which restores the score."""
    items = [item for item in difference["regressed"] if item["question"] in questions]
    drop = mean(item["base"] - item["head"] for item in items)
    if ablate is None or drop <= 0:
        return build(1, "multiple", 0.0, {**tier1, "note": "ablation unavailable"})
    head_score = mean(item["head"] for item in items)
    recovery = {
        factor: ablate(factor, [item["question"] for item in items], target) - head_score
        for factor in candidates
    }
    best = max(recovery, key=lambda factor: recovery[factor])
    share = recovery[best] / drop
    evidence = {**tier1, "recovery": recovery, "drop": drop}
    if share >= RECOVERY_SHARE:
        return build(2, best, share, evidence)
    return build(2, "multiple", 1 - share, evidence)
