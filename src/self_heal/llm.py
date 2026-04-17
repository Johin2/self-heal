"""LLM client abstraction for proposing code repairs."""

from __future__ import annotations

import os
from typing import Protocol

from anthropic import Anthropic


class LLMProposer(Protocol):
    """Anything that can turn a (system, user) prompt into a repair proposal.

    Implement this protocol to plug in OpenAI, a local model, or a test double.
    """

    def propose(self, system: str, user: str) -> str: ...


class ClaudeProposer:
    """Claude-backed implementation of `LLMProposer`.

    Reads `ANTHROPIC_API_KEY` from the environment unless `api_key` is passed.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 2048,
        api_key: str | None = None,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    def propose(self, system: str, user: str) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        for block in message.content:
            text = getattr(block, "text", None)
            if text:
                return text
        return ""
