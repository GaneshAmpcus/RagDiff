from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ragdiff.config.schema import EvalConfig
from ragdiff.errors import ConfigError


def load_config(path: str | Path) -> EvalConfig:
    config_path = Path(path)
    try:
        with config_path.open(encoding="utf-8") as stream:
            data: Any = yaml.safe_load(stream)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ConfigError("The evaluation config must contain a YAML mapping")
        return EvalConfig.model_validate(data)
    except OSError as exc:
        raise ConfigError(f"Could not read evaluation config {config_path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Could not parse evaluation config {config_path}") from exc
    except ValidationError as exc:
        raise ConfigError(f"Invalid evaluation config {config_path}: {exc}") from exc
