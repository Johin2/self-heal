"""Fireworks AI proposer (OpenAI-compatible wrapper)."""

from __future__ import annotations

import os

from self_heal.llm._openai import OpenAIProposer


class FireworksProposer(OpenAIProposer):
    """Fireworks-backed proposer.

    Thin wrapper over :class:`OpenAIProposer` with Fireworks defaults:

    - ``model`` defaults to ``accounts/fireworks/models/llama-v3p3-70b-instruct``
    - ``api_key`` defaults to ``FIREWORKS_API_KEY`` env var
    - ``base_url`` is pinned to ``https://api.fireworks.ai/inference/v1``

    Example::

        p = FireworksProposer()
        p = FireworksProposer(model="accounts/fireworks/models/qwen3-235b-a22b")
    """

    def __init__(
        self,
        model: str = "accounts/fireworks/models/llama-v3p3-70b-instruct",
        api_key: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        super().__init__(
            model=model,
            api_key=api_key or os.environ.get("FIREWORKS_API_KEY"),
            base_url="https://api.fireworks.ai/inference/v1",
            max_tokens=max_tokens,
        )
