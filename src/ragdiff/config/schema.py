from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FACTORS = frozenset({"retrieval", "prompt", "model"})


class VariantConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    app: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class EvalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app: str | None = None
    dataset: Path = Path(".ragdiff/datasets/dataset.jsonl")
    docs: list[Path] = Field(default_factory=list)
    # Directory (relative to the repo root) put on sys.path for git-ref runs.
    app_dir: Path = Path(".")
    model: str | None = None
    judge_model: str | None = None
    repeats: int = Field(default=1, ge=1)
    chunk_size: int = Field(default=1000, ge=1)
    chunk_overlap: int = Field(default=100, ge=0)
    metrics: list[str] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(default_factory=dict)
    variants: list[VariantConfig] = Field(default_factory=list)
    # Which app config keys belong to which change type; used by attribution.
    # Example: {"retrieval": ["chunk_size", "top_k"], "prompt": ["prompt"]}.
    tracked_config: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("tracked_config", mode="before")
    @classmethod
    def _normalize_tracked_config(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        unknown = sorted(set(value) - FACTORS)
        if unknown:
            raise ValueError(
                f"tracked_config keys must be among {sorted(FACTORS)}; got {unknown}"
            )
        return {
            factor: [keys] if isinstance(keys, str) else keys
            for factor, keys in value.items()
        }

    @model_validator(mode="before")
    @classmethod
    def _accept_entrypoint_alias(cls, data: Any) -> Any:
        """The design doc names the key ``entrypoint``; ``app`` is also accepted."""
        if isinstance(data, dict) and "entrypoint" in data:
            data = dict(data)
            entrypoint = data.pop("entrypoint")
            if data.get("app") not in (None, entrypoint):
                raise ValueError("'app' and 'entrypoint' disagree; use only one")
            data["app"] = entrypoint
        return data
