"""Anthropic Claude proposer."""

from __future__ import annotations

import os

try:
    from anthropic import Anthropic, AsyncAnthropic
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
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=key)
        self._aclient: AsyncAnthropic | None = None
        self._api_key = key

    @property
    def aclient(self) -> AsyncAnthropic:
        if self._aclient is None:
            self._aclient = AsyncAnthropic(api_key=self._api_key)
        return self._aclient

    def propose(self, system: str, user: str) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return _extract_text(message.content)

    async def apropose(self, system: str, user: str) -> str:
        message = await self.aclient.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return _extract_text(message.content)

    def propose_stream(self, system: str, user: str):
        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        ) as stream:
            for chunk in stream.text_stream:
                if chunk:
                    yield chunk

    async def apropose_stream(self, system: str, user: str):
        async with self.aclient.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        ) as stream:
            async for chunk in stream.text_stream:
                if chunk:
                    yield chunk


def _extract_text(content) -> str:
    for block in content:
        text = getattr(block, "text", None)
        if text:
            return text
    return ""
