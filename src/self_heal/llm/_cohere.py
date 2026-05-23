"""Cohere proposer."""

from __future__ import annotations

import os

try:
    from cohere import ClientV2
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
        self.client = ClientV2(api_key=key)

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
