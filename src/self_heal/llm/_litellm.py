"""LiteLLM proposer - universal adapter for 100+ LLM providers."""

from __future__ import annotations

try:
    from litellm import completion
except ImportError as _err:  # pragma: no cover
    raise ImportError(
        "LiteLLMProposer requires the `litellm` package. "
        "Install with: pip install 'self-heal[litellm]'"
    ) from _err


class LiteLLMProposer:
    """LiteLLM-backed proposer.

    Covers 100+ providers including OpenAI, Anthropic, Gemini, Cohere,
    Mistral, Bedrock, Vertex AI, Azure, Groq, Together, Replicate, and
    every OpenAI-compatible endpoint. Model strings follow LiteLLM
    naming conventions.

    Examples:
        # Any provider by prefix
        p = LiteLLMProposer(model="gpt-5")
        p = LiteLLMProposer(model="anthropic/claude-sonnet-4-6")
        p = LiteLLMProposer(model="gemini/gemini-2.5-pro")
        p = LiteLLMProposer(model="groq/llama-3.3-70b-versatile")
        p = LiteLLMProposer(model="mistral/mistral-large-latest")
        p = LiteLLMProposer(model="bedrock/anthropic.claude-3-5-sonnet")

    API keys are picked up from provider-specific env vars automatically
    (OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, GROQ_API_KEY, etc.).
    """

    def __init__(
        self,
        model: str,
        max_tokens: int | None = None,
        **extra_kwargs,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.extra_kwargs = extra_kwargs

    def propose(self, system: str, user: str) -> str:
        params: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **self.extra_kwargs,
        }
        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens

        response = completion(**params)
        return response.choices[0].message.content or ""
