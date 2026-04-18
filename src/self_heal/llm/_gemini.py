"""Google Gemini proposer using the google-genai SDK."""

from __future__ import annotations

import os

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError as _err:  # pragma: no cover
    raise ImportError(
        "GeminiProposer requires the `google-genai` package. "
        "Install with: pip install 'self-heal[gemini]'"
    ) from _err


class GeminiProposer:
    """Google Gemini-backed proposer.

    Reads `GEMINI_API_KEY` then `GOOGLE_API_KEY` from the environment
    unless `api_key` is passed.

    Example:
        from self_heal.llm import GeminiProposer

        proposer = GeminiProposer(model="gemini-2.5-pro")
    """

    def __init__(
        self,
        model: str = "gemini-2.5-pro",
        api_key: str | None = None,
    ):
        self.model = model
        key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )
        self.client = genai.Client(api_key=key)

    def _config(self, system: str):
        return genai_types.GenerateContentConfig(system_instruction=system)

    def propose(self, system: str, user: str) -> str:
        response = self.client.models.generate_content(
            model=self.model, contents=user, config=self._config(system),
        )
        return response.text or ""

    async def apropose(self, system: str, user: str) -> str:
        response = await self.client.aio.models.generate_content(
            model=self.model, contents=user, config=self._config(system),
        )
        return response.text or ""

    def propose_stream(self, system: str, user: str):
        for chunk in self.client.models.generate_content_stream(
            model=self.model, contents=user, config=self._config(system),
        ):
            text = getattr(chunk, "text", None)
            if text:
                yield text

    async def apropose_stream(self, system: str, user: str):
        async for chunk in await self.client.aio.models.generate_content_stream(
            model=self.model, contents=user, config=self._config(system),
        ):
            text = getattr(chunk, "text", None)
            if text:
                yield text
