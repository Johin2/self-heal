"""self-heal: automatic repair for failing Python code, powered by LLMs."""

from self_heal.core import repair
from self_heal.llm import ClaudeProposer, LLMProposer
from self_heal.loop import RepairLoop
from self_heal.types import Failure, RepairAttempt, RepairResult

__version__ = "0.0.1"

__all__ = [
    "ClaudeProposer",
    "Failure",
    "LLMProposer",
    "RepairAttempt",
    "RepairLoop",
    "RepairResult",
    "repair",
]
