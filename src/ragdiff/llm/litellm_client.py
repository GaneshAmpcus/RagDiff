from importlib import import_module

from ragdiff.errors import IntegrationError


class LiteLLMClient:
    def complete(self, prompt: str, *, model: str) -> str:
        try:
            litellm = import_module("litellm")
        except ImportError as exc:
            raise IntegrationError(
                "LiteLLM is required for this provider; install ragdiff[llm]"
            ) from exc
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content
        if not isinstance(content, str):
            raise IntegrationError("The LLM provider returned no text content")
        return content
