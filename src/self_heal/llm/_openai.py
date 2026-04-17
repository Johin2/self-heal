"""OpenAI proposer (also supports any OpenAI-compatible endpoint)."""

from __future__ import annotations

import os

try:
    from openai import OpenAI
except ImportError as _err:  # pragma: no cover
    raise ImportError(
        "OpenAIProposer requires the `openai` package. "
        "Install with: pip install 'self-heal[openai]'"
    ) from _err


class OpenAIProposer:
    """OpenAI-backed proposer.

    Also works with any OpenAI-compatible endpoint — pass `base_url`.
    Covers OpenRouter, Together, Fireworks, Groq, Anyscale, Perplexity,
    xAI, DeepSeek, Azure OpenAI, local Ollama, LM Studio, vLLM, and
    llama.cpp server.

    Examples:
        # OpenAI
        p = OpenAIProposer(model="gpt-5")

        # OpenRouter (hundreds of models through one endpoint)
        p = OpenAIProposer(
            model="google/gemini-2.5-pro",
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-or-...",
        )

        # Groq
        p = OpenAIProposer(
            model="llama-3.3-70b-versatile",
            base_url="https://api.groq.com/openai/v1",
            api_key="gsk_...",
        )

        # Local Ollama
        p = OpenAIProposer(
            model="llama3.3",
            base_url="http://localhost:11434/v1",
            api_key="ollama",
        )
    """

    def __init__(
        self,
        model: str = "gpt-5",
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int | None = None,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=base_url,
        )

    def propose(self, system: str, user: str) -> str:
        params: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.max_tokens is not None:
            params["max_completion_tokens"] = self.max_tokens

        completion = self.client.chat.completions.create(**params)
        choice = completion.choices[0]
        return choice.message.content or ""
