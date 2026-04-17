"""Failure classification."""

from __future__ import annotations

import traceback as tb
from typing import Any

from self_heal.types import Failure, FailureKind


def _classify_kind(exc: BaseException) -> FailureKind:
    if isinstance(exc, AssertionError):
        return "assertion"
    if isinstance(exc, (ValueError, TypeError, KeyError, IndexError, AttributeError)):
        return "validation"
    return "exception"


def classify(exc: BaseException, inputs: dict[str, Any] | None = None) -> Failure:
    """Capture a failure with enough context to repair it."""
    return Failure(
        kind=_classify_kind(exc),
        error_type=type(exc).__name__,
        message=str(exc),
        traceback="".join(tb.format_exception(type(exc), exc, exc.__traceback__)),
        inputs=inputs or {},
    )
