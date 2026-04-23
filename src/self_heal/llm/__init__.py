"""LLM proposer adapters for self-heal.

Install only the adapters you need:

    pip install 'self-heal[claude]'    # Anthropic Claude
    pip install 'self-heal[openai]'    # OpenAI + OpenAI-compatible endpoints
    pip install 'self-heal[gemini]'    # Google Gemini
    pip install 'self-heal[litellm]'   # 100+ providers via LiteLLM
    pip install 'self-heal[all]'       # everything

Each adapter lazily imports its SDK, so missing SDKs never break `import self_heal`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from self_heal.llm._claude import ClaudeProposer
    from self_heal.llm._fireworks import FireworksProposer
    from self_heal.llm._gemini import GeminiProposer
    from self_heal.llm._litellm import LiteLLMProposer
    from self_heal.llm._openai import OpenAIProposer
    from self_heal.llm._together import TogetherProposer


class LLMProposer(Protocol):
    """Anything that turns a (system, user) prompt into a repair proposal.

    Implement this protocol to plug any LLM into self-heal. `propose` is
    required; `apropose` and `propose_stream` are optional and improve
    async / streaming paths when present.
    """

    def propose(self, system: str, user: str) -> str: ...

    # Optional: native async. When absent, RepairLoop.arun falls back to
    # asyncio.to_thread(propose). Declared here for static reference;
    # concrete duck-typing is checked with hasattr.
    # async def apropose(self, system: str, user: str) -> str: ...

    # Optional: streaming. When absent, RepairLoop treats propose() as a
    # single-chunk generator.
    # def propose_stream(self, system: str, user: str) -> Iterator[str]: ...


def __getattr__(name: str) -> Any:
    if name == "ClaudeProposer":
        from self_heal.llm._claude import ClaudeProposer

        return ClaudeProposer
    if name == "FireworksProposer":
        from self_heal.llm._fireworks import FireworksProposer

        return FireworksProposer
    if name == "GeminiProposer":
        from self_heal.llm._gemini import GeminiProposer

        return GeminiProposer
    if name == "LiteLLMProposer":
        from self_heal.llm._litellm import LiteLLMProposer

        return LiteLLMProposer
    if name == "OpenAIProposer":
        from self_heal.llm._openai import OpenAIProposer

        return OpenAIProposer
    if name == "TogetherProposer":
        from self_heal.llm._together import TogetherProposer

        return TogetherProposer
    raise AttributeError(f"module 'self_heal.llm' has no attribute {name!r}")


__all__ = [
    "ClaudeProposer",
    "FireworksProposer",
    "GeminiProposer",
    "LLMProposer",
    "LiteLLMProposer",
    "OpenAIProposer",
    "TogetherProposer",
]
