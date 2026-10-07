from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
    model: str | None = None
    repeats: int = Field(default=1, ge=1)
    chunk_size: int = Field(default=1000, ge=1)
    chunk_overlap: int = Field(default=100, ge=0)
    metrics: list[str] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(default_factory=dict)
    variants: list[VariantConfig] = Field(default_factory=list)
