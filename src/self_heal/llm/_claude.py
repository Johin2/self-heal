"""Anthropic Claude proposer."""

from __future__ import annotations

import os

try:
    from anthropic import Anthropic
except ImportError as _err:  # pragma: no cover
    raise ImportError(
        "ClaudeProposer requires the `anthropic` package. "
        "Install with: pip install 'self-heal[claude]'"
    ) from _err


class ClaudeProposer:
    """Anthropic Claude-backed proposer.

    Reads `ANTHROPIC_API_KEY` from the environment unless `api_key` is passed.

    Example:
        from self_heal.llm import ClaudeProposer

        proposer = ClaudeProposer(model="claude-sonnet-4-6")
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
