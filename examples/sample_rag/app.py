from ragdiff import RunOutput


def run(question: str, config: dict) -> RunOutput:
    return RunOutput(
        answer=f"Sample response to: {question}",
        contexts=[],
        metadata={"app": "sample_rag"},
    )
