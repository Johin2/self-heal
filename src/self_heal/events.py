"""Event types + callback hook for observable repairs.

Pass `on_event=callable` to `RepairLoop` or `@repair`. The callable
receives a `RepairEvent` on every significant step. Agent UIs can stream
progress; observability backends can record metrics.

Token-level streaming is live: proposers that implement `propose_stream`
or `apropose_stream` emit `propose_chunk` events for each delta. Falls
back to discrete events if streaming is unavailable or raises.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from self_heal.types import Failure

EventType = Literal[
    "attempt_start",
    "attempt_failed",
    "propose_start",
    "propose_chunk",
    "propose_complete",
    "stream_error",
    "install_success",
    "install_failed",
    "cache_hit",
    "cache_miss",
    "safety_violation",
    "verify_success",
    "repair_succeeded",
    "repair_exhausted",
    "transient_retry",
]


@dataclass
class RepairEvent:
    """A single observable moment in a repair loop."""

    type: EventType
    attempt_number: int | None = None
    failure: Failure | None = None
    proposed_source: str | None = None
    error: str | None = None
    delta: str | None = None
    retry_attempt: int | None = None
    retry_delay: float | None = None
    extra: dict[str, Any] | None = None


EventCallback = Callable[[RepairEvent], None]


def emit(callback: EventCallback | None, event: RepairEvent) -> None:
    """Safely invoke a callback, swallowing observer errors so bad
    hooks can't break a repair loop."""
    if callback is None:
        return
    with contextlib.suppress(Exception):
        callback(event)
