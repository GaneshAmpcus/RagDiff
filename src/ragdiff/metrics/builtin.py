from ragdiff.metrics.base import Metric
from ragdiff.metrics.lexical import LEXICAL_METRICS
from ragdiff.metrics.ragas_metrics import build_ragas_metrics


def build_builtin_metrics(
    names: list[str], *, judge_model: str | None = None
) -> list[Metric]:
    """Lexical (free) metrics first; everything else goes to the Ragas adapters."""
    ragas_names = [name for name in names if name not in LEXICAL_METRICS]
    ragas = {
        metric.name: metric
        for metric in (
            build_ragas_metrics(ragas_names, judge_model=judge_model)
            if ragas_names
            else []
        )
    }
    return [
        LEXICAL_METRICS[name]() if name in LEXICAL_METRICS else ragas[name]
        for name in names
    ]
