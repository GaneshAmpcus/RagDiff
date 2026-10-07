from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from ragdiff.errors import AppLoadError


@dataclass(slots=True)
class RunOutput:
    answer: str
    contexts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_value(cls, value: RunOutput | Mapping[str, Any] | str) -> RunOutput:
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            return cls(answer=value)
        if not isinstance(value, Mapping):
            raise TypeError("App output must be RunOutput, a mapping, or a string")
        answer = value.get("answer")
        if not isinstance(answer, str):
            raise TypeError("App output mapping must contain a string 'answer'")
        contexts = value.get("contexts", [])
        metadata = value.get("metadata", {})
        if not isinstance(contexts, list) or not all(
            isinstance(context, str) for context in contexts
        ):
            raise TypeError("'contexts' must be a list of strings")
        if not isinstance(metadata, dict):
            raise TypeError("'metadata' must be a dictionary")
        return cls(answer=answer, contexts=contexts, metadata=metadata)


App = Callable[[str, dict[str, Any]], RunOutput | Mapping[str, Any] | str]


def load_app(entrypoint: str) -> App:
    """Load an application callable using ``module:attribute`` syntax."""
    module_name, separator, attribute = entrypoint.partition(":")
    if not separator or not module_name or not attribute:
        raise AppLoadError(
            f"Invalid app entrypoint {entrypoint!r}; expected 'module:callable'"
        )
    try:
        module = importlib.import_module(module_name)
        app = getattr(module, attribute)
    except (ImportError, AttributeError) as exc:
        raise AppLoadError(f"Could not load app entrypoint {entrypoint!r}") from exc
    if not callable(app):
        raise AppLoadError(f"App entrypoint {entrypoint!r} is not callable")
    return cast(App, app)
