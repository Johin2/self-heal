"""Cohere proposer."""

from __future__ import annotations

import os

try:
    from cohere import AsyncClientV2, ClientV2
except ImportError as _err:  # pragma: no cover
    raise ImportError(
        "CohereProposer requires the `cohere` package. "
        "Install with: pip install 'self-heal-llm[cohere]'"
    ) from _err


class CohereProposer:
    """Cohere-backed proposer using the native Cohere SDK.

    Reads `COHERE_API_KEY` from the environment unless `api_key` is passed.

    Example:
        from self_heal.llm import CohereProposer

        proposer = CohereProposer(model="command-r-plus")
    """

    def __init__(
        self,
        model: str = "command-r-plus",
        api_key: str | None = None,
        max_tokens: int | None = None,
    ):
        self.model = model
        self.max_tokens = max_tokens
        key = api_key or os.environ.get("COHERE_API_KEY")
        self._api_key = key
        self.client = ClientV2(api_key=key)
        self._aclient: AsyncClientV2 | None = None

    @property
    def aclient(self) -> AsyncClientV2:
        if self._aclient is None:
            self._aclient = AsyncClientV2(api_key=self._api_key)
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
            params["max_tokens"] = self.max_tokens
        return params

    def propose(self, system: str, user: str) -> str:
        response = self.client.chat(**self._params(system, user))
        return _extract_text(response)

    async def apropose(self, system: str, user: str) -> str:
        response = await self.aclient.chat(**self._params(system, user))
        return _extract_text(response)

    def propose_stream(self, system: str, user: str):
        stream = self.client.chat_stream(**self._params(system, user))
        for chunk in stream:
            delta = _extract_delta_text(chunk)
            if delta:
                yield delta

    async def apropose_stream(self, system: str, user: str):
        stream = self.aclient.chat_stream(**self._params(system, user))
        async for chunk in stream:
            delta = _extract_delta_text(chunk)
            if delta:
                yield delta


def _extract_text(response) -> str:
    message = getattr(response, "message", None)
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if not content:
        return ""
    for block in content:
        text = getattr(block, "text", None)
        if text:
            return text
    return ""


def _extract_delta_text(chunk) -> str:
    delta = getattr(chunk, "delta", None)
    message = getattr(delta, "message", None)
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if not content:
        return ""
    for block in content:
        text = getattr(block, "text", None)
        if text:
            return text
    return ""
