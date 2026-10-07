from collections.abc import Sequence
from pathlib import Path


def read_documents(paths: Sequence[str | Path]) -> list[tuple[Path, str]]:
    documents: list[tuple[Path, str]] = []
    for item in paths:
        path = Path(item)
        candidates = sorted(path.rglob("*")) if path.is_dir() else [path]
        for candidate in candidates:
            if candidate.is_file():
                documents.append((candidate, candidate.read_text(encoding="utf-8")))
    return documents


def split_text(text: str, *, chunk_size: int, overlap: int = 0) -> list[str]:
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")
    cleaned = text.strip()
    if not cleaned:
        return []
    step = chunk_size - overlap
    return [cleaned[start : start + chunk_size] for start in range(0, len(cleaned), step)]
