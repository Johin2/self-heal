"""self-heal: automatic repair for failing Python code, powered by any LLM."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from self_heal.cache import RepairCache
from self_heal.core import repair
from self_heal.events import EventCallback, RepairEvent
from self_heal.llm import LLMProposer
from self_heal.loop import RepairLoop
from self_heal.safety import SafetyConfig, UnsafeProposalError
from self_heal.types import Failure, RepairAttempt, RepairResult
from self_heal.verify import Test, Verifier, check_tests, check_verifier

if TYPE_CHECKING:
    from self_heal.llm import (
        ClaudeProposer,
        FireworksProposer,
        GeminiProposer,
        LiteLLMProposer,
        OpenAIProposer,
        TogetherProposer,
    )

__version__ = "0.4.2"


def __getattr__(name: str) -> Any:
    if name in {
        "ClaudeProposer",
        "FireworksProposer",
        "GeminiProposer",
        "LiteLLMProposer",
        "OpenAIProposer",
        "TogetherProposer",
    }:
        from self_heal import llm

        return getattr(llm, name)
    raise AttributeError(f"module 'self_heal' has no attribute {name!r}")


__all__ = [
    "ClaudeProposer",
    "EventCallback",
    "Failure",
    "FireworksProposer",
    "GeminiProposer",
    "LLMProposer",
    "LiteLLMProposer",
    "OpenAIProposer",
    "RepairAttempt",
    "RepairCache",
    "RepairEvent",
    "RepairLoop",
    "RepairResult",
    "SafetyConfig",
    "Test",
    "TogetherProposer",
    "UnsafeProposalError",
    "Verifier",
    "check_tests",
    "check_verifier",
    "repair",
]
