from ragdiff.errors import ConfigError
from ragdiff.metrics.base import Metric


class MetricRegistry:
    def __init__(self) -> None:
        self._metrics: dict[str, Metric] = {}

    def register(self, metric: Metric) -> None:
        if metric.name in self._metrics:
            raise ConfigError(f"Metric {metric.name!r} is already registered")
        self._metrics[metric.name] = metric

    def get(self, name: str) -> Metric:
        try:
            return self._metrics[name]
        except KeyError as exc:
            raise ConfigError(f"Metric {name!r} is not registered") from exc
