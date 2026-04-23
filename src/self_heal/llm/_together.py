"""Together AI proposer (OpenAI-compatible wrapper)."""

from __future__ import annotations

import os

from self_heal.llm._openai import OpenAIProposer


class TogetherProposer(OpenAIProposer):
    """Together-backed proposer.

    Thin wrapper over :class:`OpenAIProposer` with Together defaults:

    - ``model`` defaults to ``meta-llama/Llama-3.3-70B-Instruct-Turbo``
    - ``api_key`` defaults to ``TOGETHER_API_KEY`` env var
    - ``base_url`` is pinned to ``https://api.together.xyz/v1``

    Example::

        p = TogetherProposer()
        p = TogetherProposer(model="meta-llama/Llama-3.1-70B-Instruct-Turbo")
    """

    def __init__(
        self,
        model: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        api_key: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        resolved_key = api_key or os.environ.get("TOGETHER_API_KEY")
        if resolved_key is None:
            raise ValueError(
                "TogetherProposer requires a Together API key. "
                "Set TOGETHER_API_KEY or pass api_key=...; "
                "OPENAI_API_KEY is intentionally NOT used here."
            )
        super().__init__(
            model=model,
            api_key=resolved_key,
            base_url="https://api.together.xyz/v1",
            max_tokens=max_tokens,
        )
