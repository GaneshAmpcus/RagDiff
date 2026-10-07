from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def run_ablation(components: list[T], evaluate: Callable[[list[T]], float]) -> dict[str, float]:
    full_score = evaluate(components)
    return {
        str(component): full_score - evaluate(
            [candidate for candidate in components if candidate != component]
        )
        for component in components
    }
