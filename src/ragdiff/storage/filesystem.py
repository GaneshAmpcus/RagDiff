import json
from pathlib import Path
from typing import Any

from ragdiff.errors import StorageError


class FileSystemStorage:
    def __init__(self, root: str | Path = ".ragdiff") -> None:
        self.root = Path(root)

    def write_jsonl(self, path: str | Path, records: list[dict[str, Any]]) -> None:
        destination = self._resolve(path)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("w", encoding="utf-8") as stream:
                for record in records:
                    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            raise StorageError(f"Could not write records to {destination}") from exc

    def write_text(self, path: str | Path, value: str) -> None:
        destination = self._resolve(path)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(value, encoding="utf-8")
        except OSError as exc:
            raise StorageError(f"Could not write text to {destination}") from exc

    def read_text(self, path: str | Path) -> str:
        source = self._resolve(path)
        try:
            return source.read_text(encoding="utf-8")
        except OSError as exc:
            raise StorageError(f"Could not read text from {source}") from exc

    def write_json(self, path: str | Path, value: dict[str, Any]) -> None:
        self.write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")

    def read_json(self, path: str | Path) -> dict[str, Any]:
        source = self._resolve(path)
        try:
            value = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"Could not read JSON from {source}") from exc
        if not isinstance(value, dict):
            raise StorageError(f"Expected a JSON object in {source}")
        return value

    def read_jsonl(self, path: str | Path) -> list[dict[str, Any]]:
        source = self._resolve(path)
        try:
            with source.open(encoding="utf-8") as stream:
                records = [json.loads(line) for line in stream if line.strip()]
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"Could not read records from {source}") from exc
        if not all(isinstance(record, dict) for record in records):
            raise StorageError(f"Expected JSON objects in {source}")
        return records

    def _resolve(self, path: str | Path) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else self.root / candidate
