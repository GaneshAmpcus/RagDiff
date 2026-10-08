"""Deterministic sample RAG app: keyword retrieval, no LLM or network needed.

It honours ``chunk_size`` and ``top_k`` from the RAGDiff ``config`` argument so a
change to retrieval settings produces a real, measurable difference in contexts.
"""

import re
from pathlib import Path

from ragdiff import RunOutput

DOCS_DIR = Path(__file__).parent / "docs"
DEFAULTS = {"chunk_size": 800, "top_k": 3}


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _chunks(chunk_size: int) -> list[str]:
    chunks: list[str] = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        chunks.extend(
            text[start : start + chunk_size] for start in range(0, len(text), chunk_size)
        )
    return chunks


def run(question: str, config: dict | None = None) -> RunOutput:
    settings = {**DEFAULTS, **(config or {})}
    chunk_size, top_k = int(settings["chunk_size"]), int(settings["top_k"])
    query = _tokens(question)
    ranked = sorted(
        _chunks(chunk_size),
        key=lambda chunk: len(query & _tokens(chunk)),
        reverse=True,
    )
    contexts = [chunk for chunk in ranked[:top_k] if query & _tokens(chunk)]
    answer = contexts[0].splitlines()[0] if contexts else "I don't know."
    return RunOutput(
        answer=answer,
        contexts=contexts,
        metadata={"app": "sample_rag", "chunk_size": chunk_size, "top_k": top_k},
    )
