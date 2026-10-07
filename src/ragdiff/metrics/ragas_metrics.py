from importlib import import_module

from ragdiff.bootstrap.dataset import DatasetCase
from ragdiff.contract import RunOutput
from ragdiff.errors import IntegrationError


class RagasMetric:
    """Evaluate one supported Ragas metric for a single case."""

    def __init__(self, name: str) -> None:
        try:
            self._ragas = import_module("ragas")
            metrics_module = import_module("ragas.metrics")
        except ImportError as exc:
            raise IntegrationError(
                "Ragas is required for this adapter; install ragdiff[metrics]"
            ) from exc
        metric = getattr(metrics_module, name, None)
        if metric is None:
            raise IntegrationError(f"Ragas does not provide a metric named {name!r}")
        self.name = name
        self._metric = metric

    def score(self, case: DatasetCase, output: RunOutput) -> float:
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
            result = self._ragas.evaluate(dataset, metrics=[self._metric])
            score = result[self.name][0]
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise IntegrationError(
                f"Ragas failed to score metric {self.name!r}"
            ) from exc
        if not isinstance(score, (int, float)):
            raise IntegrationError(
                f"Ragas returned a non-numeric score for metric {self.name!r}"
            )
        return float(score)
