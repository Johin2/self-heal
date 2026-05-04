"""Groq proposer (OpenAI-compatible)."""

from __future__ import annotations

import os

from self_heal.llm._openai import OpenAIProposer


class GroqProposer(OpenAIProposer):
    """Groq-backed proposer over the OpenAI-compatible endpoint.

    Reads `GROQ_API_KEY` from the environment unless `api_key` is passed.
    Defaults `base_url` to `https://api.groq.com/openai/v1` and uses Groq's
    Llama 3.3 70B as the default model. Otherwise behaves exactly like
    `OpenAIProposer`.

    Example:
        from self_heal.llm import GroqProposer

        proposer = GroqProposer()
        proposer = GroqProposer(model="llama-3.1-8b-instant")
    """

    def __init__(
        self,
        model: str = "llama-3.3-70b-versatile",
        api_key: str | None = None,
        max_tokens: int | None = None,
    ):
        super().__init__(
            model=model,
            api_key=api_key or os.environ.get("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
            max_tokens=max_tokens,
        )
