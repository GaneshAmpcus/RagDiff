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
