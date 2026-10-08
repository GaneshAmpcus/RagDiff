"""Free, deterministic, LLM-free metrics: token recall of the reference answer."""

from __future__ import annotations

import re

from ragdiff.bootstrap.dataset import DatasetCase
from ragdiff.contract import RunOutput
from ragdiff.errors import IntegrationError

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


class _ReferenceRecall:
    """Fraction of the reference answer's tokens found in some part of the output."""

    name = ""

    def _haystack(self, output: RunOutput) -> str:
        raise NotImplementedError

    def score(self, case: DatasetCase, output: RunOutput) -> float:
        if not case.reference:
            raise IntegrationError(
                f"Metric {self.name!r} needs a reference answer, but the case "
                f"{case.question!r} has none"
            )
        wanted = _tokens(case.reference)
        if not wanted:
            return 1.0
        return len(wanted & _tokens(self._haystack(output))) / len(wanted)


class AnswerContainsReference(_ReferenceRecall):
    name = "answer_contains_reference"

    def _haystack(self, output: RunOutput) -> str:
        return output.answer


class ContextContainsReference(_ReferenceRecall):
    """A free retrieval proxy: did the retrieved contexts hold the answer?"""

    name = "context_contains_reference"

    def _haystack(self, output: RunOutput) -> str:
        return " ".join(output.contexts)


LEXICAL_METRICS: dict[str, type[_ReferenceRecall]] = {
    AnswerContainsReference.name: AnswerContainsReference,
    ContextContainsReference.name: ContextContainsReference,
}
