"""OpenAI proposer (also supports any OpenAI-compatible endpoint)."""

from __future__ import annotations

import os

try:
    from openai import AsyncOpenAI, OpenAI
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
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._api_key = resolved_key
        self._base_url = base_url
        self.client = OpenAI(api_key=resolved_key, base_url=base_url)
        self._aclient: AsyncOpenAI | None = None

    @property
    def aclient(self) -> AsyncOpenAI:
        if self._aclient is None:
            self._aclient = AsyncOpenAI(
                api_key=self._api_key, base_url=self._base_url
            )
        return self._aclient

    def _params(self, system: str, user: str) -> dict:
        params: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.max_tokens is not None:
            params["max_completion_tokens"] = self.max_tokens
        return params

    def propose(self, system: str, user: str) -> str:
        completion = self.client.chat.completions.create(**self._params(system, user))
        return completion.choices[0].message.content or ""

    async def apropose(self, system: str, user: str) -> str:
        completion = await self.aclient.chat.completions.create(
            **self._params(system, user)
        )
        return completion.choices[0].message.content or ""

    def propose_stream(self, system: str, user: str):
        stream = self.client.chat.completions.create(
            stream=True, **self._params(system, user)
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def apropose_stream(self, system: str, user: str):
        stream = await self.aclient.chat.completions.create(
            stream=True, **self._params(system, user)
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
