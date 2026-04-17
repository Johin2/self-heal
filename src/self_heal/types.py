"""Data models for self-heal."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FailureKind = Literal[
    "exception",
    "assertion",
    "validation",
    "verifier",
    "test",
    "unknown",
]


class Failure(BaseModel):
    """A captured failure with enough context to propose a repair."""

    kind: FailureKind
    error_type: str
    message: str
    traceback: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)


class RepairAttempt(BaseModel):
    """One attempt in a repair loop."""

    attempt_number: int
    failure: Failure
    proposed_source: str | None = None
    succeeded: bool = False
    error_after_repair: str | None = None


class RepairResult(BaseModel):
    """The outcome of a repair loop."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    succeeded: bool
    final_value: Any = None
    attempts: list[RepairAttempt] = Field(default_factory=list)
    total_attempts: int = 0
