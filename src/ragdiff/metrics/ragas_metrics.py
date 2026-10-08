from collections.abc import Sequence
from importlib import import_module
from typing import Any

from ragdiff.bootstrap.dataset import DatasetCase
from ragdiff.contract import RunOutput
from ragdiff.errors import ConfigError, IntegrationError
from ragdiff.metrics.base import Metric

# RAGDiff-facing names (as written in evals.yaml) -> Ragas metric attribute names.
RAGAS_ALIASES: dict[str, str] = {
    "faithfulness": "faithfulness",
    "answer_relevance": "answer_relevancy",
    "answer_relevancy": "answer_relevancy",
    "context_recall": "context_recall",
    "context_precision": "context_precision",
}
# Metrics that need no reference answer; these are the Phase 1 defaults.
REFERENCE_FREE = {"faithfulness", "answer_relevance", "answer_relevancy"}


class RagasMetric:
    """Evaluate one supported Ragas metric for a single case."""

    def __init__(self, name: str, *, judge_model: str | None = None) -> None:
        ragas_name = RAGAS_ALIASES.get(name, name)
        try:
            self._ragas = import_module("ragas")
            metrics_module = import_module("ragas.metrics")
        except ImportError as exc:
            raise IntegrationError(
                "Ragas is required for this adapter; install ragdiff[metrics]"
            ) from exc
        metric = getattr(metrics_module, ragas_name, None)
        if metric is None:
            raise IntegrationError(f"Ragas does not provide a metric named {name!r}")
        self.name = name
        self.requires_reference = name not in REFERENCE_FREE
        self._ragas_name = ragas_name
        self._metric = metric
        self._judge = self._build_judge(judge_model)

    @staticmethod
    def _build_judge(judge_model: str | None) -> Any:
        """Pin the judge model (temperature 0) instead of Ragas' implicit default."""
        if judge_model is None:
            return None
        try:
            chat = import_module("langchain_openai").ChatOpenAI
        except ImportError as exc:
            raise IntegrationError(
                "Pinning a judge model with Ragas 0.1.x needs langchain-openai"
            ) from exc
        return chat(model=judge_model, temperature=0)

    def score(self, case: DatasetCase, output: RunOutput) -> float:
        if self.requires_reference and not case.reference:
            raise IntegrationError(
                f"Metric {self.name!r} needs a reference answer, but the case "
                f"{case.question!r} has none"
            )
        try:
            datasets = import_module("datasets")
            dataset = datasets.Dataset.from_list(
                [
                    {
                        "question": case.question,
                        "answer": output.answer,
                        "contexts": output.contexts,
                        "ground_truth": case.reference or "",
                    }
                ]
            )
            kwargs: dict[str, Any] = {"metrics": [self._metric]}
            if self._judge is not None:
                kwargs["llm"] = self._judge
            result = self._ragas.evaluate(dataset, **kwargs)
            score = result[self._ragas_name]
            if isinstance(score, Sequence) and not isinstance(score, str):
                score = score[0]
        except (AttributeError, KeyError, TypeError, ValueError, IndexError) as exc:
            raise IntegrationError(
                f"Ragas failed to score metric {self.name!r}"
            ) from exc
        if not isinstance(score, (int, float)):
            raise IntegrationError(
                f"Ragas returned a non-numeric score for metric {self.name!r}"
            )
        return float(score)


def build_ragas_metrics(
    names: list[str], *, judge_model: str | None = None
) -> list[Metric]:
    unknown = [name for name in names if name not in RAGAS_ALIASES]
    if unknown:
        raise ConfigError(
            "No built-in implementation for metric(s): "
            + ", ".join(sorted(unknown))
            + ". Pass a custom Metric through the Python API."
        )
    return [RagasMetric(name, judge_model=judge_model) for name in names]
