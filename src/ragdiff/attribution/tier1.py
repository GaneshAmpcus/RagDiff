"""Tier 1 attribution: compare retrieved contexts between base and head. Free."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ragdiff.runner.executor import RunRecord


@dataclass(slots=True)
class QuestionEvidence:
    question: str
    changed: bool
    lost: list[str] = field(default_factory=list)
    gained: list[str] = field(default_factory=list)


def _contexts(records: list[RunRecord], variant: str) -> dict[str, list[str]]:
    """Contexts per question from each question's first repeat of ``variant``."""
    result: dict[str, list[str]] = {}
    for record in sorted(records, key=lambda item: item.repeat):
        if record.variant == variant:
            result.setdefault(record.question, record.contexts)
    return result


def classify_questions(
    records: list[RunRecord],
    questions: list[str],
    *,
    base: str,
    head: str,
) -> list[QuestionEvidence]:
    base_contexts = _contexts(records, base)
    head_contexts = _contexts(records, head)
    evidence: list[QuestionEvidence] = []
    for question in questions:
        if question not in base_contexts or question not in head_contexts:
            continue
        before = {item.strip() for item in base_contexts[question]}
        after = {item.strip() for item in head_contexts[question]}
        evidence.append(
            QuestionEvidence(
                question=question,
                changed=before != after,
                lost=sorted(before - after),
                gained=sorted(after - before),
            )
        )
    return evidence


def summarize_evidence(evidence: list[QuestionEvidence]) -> dict[str, Any]:
    total = len(evidence)
    changed = sum(1 for item in evidence if item.changed)
    return {
        "questions": total,
        "contexts_changed": changed,
        "share_retrieval": changed / total if total else 0.0,
    }
