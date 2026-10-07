from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Protocol

from ragdiff.llm.base import LLMClient


class Cache(Protocol):
    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str) -> None: ...


class DiskCache:
    def __init__(self, directory: str | Path = ".ragdiff/cache") -> None:
        self.directory = Path(directory)

    def get(self, key: str) -> str | None:
        path = self._path_for(key)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        value = data["value"]
        if not isinstance(value, str):
            raise TypeError(f"Invalid cache value in {path}")
        return value

    def set(self, key: str, value: str) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"value": value}, ensure_ascii=False), encoding="utf-8"
        )

    def _path_for(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.json"


class CachedLLMClient:
    def __init__(self, client: LLMClient, cache: Cache) -> None:
        self._client = client
        self._cache = cache
        self._logger = logging.getLogger("ragdiff.llm.cache")

    def complete(self, prompt: str, *, model: str) -> str:
        key = f"{model}\0{prompt}"
        cached = self._cache.get(key)
        if cached is not None:
            self._logger.debug(
                "LLM response cache hit",
                extra={"event": "cache_hit", "cache_hit": True},
            )
            return cached
        self._logger.debug(
            "LLM response cache miss",
            extra={"event": "cache_miss", "cache_hit": False},
        )
        response = self._client.complete(prompt, model=model)
        self._cache.set(key, response)
        return response
