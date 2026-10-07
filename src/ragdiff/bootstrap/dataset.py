from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ragdiff.errors import ConfigError


class DatasetCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    reference: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def read_dataset(path: str | Path) -> list[DatasetCase]:
    dataset_path = Path(path)
    cases: list[DatasetCase] = []
    try:
        with dataset_path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    cases.append(DatasetCase.model_validate_json(line))
                except ValidationError as exc:
                    raise ConfigError(
                        f"Invalid dataset record on line {line_number} "
                        f"of {dataset_path}: {exc}"
                    ) from exc
    except OSError as exc:
        raise ConfigError(f"Could not read dataset {dataset_path}") from exc
    return cases


def write_dataset(path: str | Path, cases: list[DatasetCase]) -> None:
    dataset_path = Path(path)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    with dataset_path.open("w", encoding="utf-8") as stream:
        for case in cases:
            stream.write(json.dumps(case.model_dump(), ensure_ascii=False) + "\n")
