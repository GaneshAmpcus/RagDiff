from dataclasses import dataclass, field
from typing import Any

from ragdiff.contract import App


@dataclass(slots=True)
class Variant:
    name: str
    app: App
    config: dict[str, Any] = field(default_factory=dict)
