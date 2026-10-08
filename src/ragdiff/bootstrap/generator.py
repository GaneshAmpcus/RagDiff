import json
import re

from ragdiff.llm.base import LLMClient


def generate_questions(
    document: str, *, client: LLMClient, model: str, count: int = 3
) -> list[str]:
    if count < 1:
        raise ValueError("count must be positive")
    prompt = (
        f"Write exactly {count} distinct questions answerable from this document. "
        "Return one question per line and no numbering.\n\n"
        f"{document}"
    )
    questions = [
        line.strip().lstrip("-*0123456789. ")
        for line in client.complete(prompt, model=model).splitlines()
        if line.strip()
    ]
    return questions[:count]


def generate_qa_pairs(
    document: str, *, client: LLMClient, model: str, count: int = 3
) -> list[tuple[str, str]]:
    """Ask the LLM for question/answer pairs grounded only in ``document``.

    Malformed items are dropped rather than raised, because LLM output is noisy
    and a reviewer sees the resulting dataset anyway.
    """
    if count < 1:
        raise ValueError("count must be positive")
    prompt = (
        f"Write exactly {count} distinct question/answer pairs that can be answered "
        "using ONLY the document below. Return a JSON array of objects with the "
        'keys "question" and "answer" and nothing else.\n\n'
        f"{document}"
    )
    raw = client.complete(prompt, model=model)
    match = re.search(r"\[.*\]", raw, flags=re.DOTALL)
    if match is None:
        return []
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    pairs: list[tuple[str, str]] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        question, answer = item.get("question"), item.get("answer")
        if (
            isinstance(question, str)
            and isinstance(answer, str)
            and question.strip()
            and answer.strip()
        ):
            pairs.append((question.strip(), answer.strip()))
    return pairs[:count]
