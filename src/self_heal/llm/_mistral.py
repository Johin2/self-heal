Blame
"""Mistral AI proposer."""

from __future__ import annotations

import os

try:
    from mistralai import Mistral
except ImportError as _err:  # pragma: no cover
    raise ImportError(
        "MistralProposer requires the `mistralai` package. "
        "Install with: pip install 'self-heal[mistralai]'"
    ) from _err


class MistralProposer:
    """Mistral AI-backed proposer.

    Reads `MISTRAL_API_KEY` from the environment unless `api_key` is passed.

    Example:
        from self_heal.llm import MistralProposer

        proposer = MistralProposer(model="mistral-large-latest")
"""

    def __init__(
        self,
        model: str = "mistral-large-latest",
        max_tokens: int = 2048,
        api_key: str | None = None,
    ):
        self.model = model
        self.max_tokens = max_tokens
        key = api_key or os.environ.get("MISTRAL_API_KEY")
        self.client = Mistral(api_key=key)
        self._api_key = key
        self._aclient: Mistral | None = None

    @property
    def aclient(self) -> Mistral:
        if self._aclient is None:
            self._aclient = Mistral(api_key=self._api_key)
        return self._aclient

    def propose(self, system: str, user: str) -> str:
        message = self.client.chat.complete(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
        )
        return _extract_text(message)

    async def apropose(self, system: str, user: str) -> str:
        message = await self.aclient.chat.complete(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
        )
        return _extract_text(message)
        
    def propose_stream(self, system: str, user: str):
        stream = self.client.chat.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
        )
        for chunk in stream:
            if chunk.data.choices[0].delta.content:
                yield chunk.data.choices[0].delta.content

    async def apropose_stream(self, system: str, user: str):
        stream = await self.aclient.chat.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
        )
        async for chunk in stream:
            if chunk.data.choices[0].delta.content:
                yield chunk.data.choices[0].delta.content

def _extract_text(response) -> str:
    try:
        return response.choices[0].message.content
    except (AttributeError, IndexError):
        return ""
