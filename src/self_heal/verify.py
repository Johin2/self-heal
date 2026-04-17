"""Result verification helpers: predicates + test suites."""

from __future__ import annotations

import traceback as tb
from collections.abc import Callable
from typing import Any

from self_heal.types import Failure

# A verifier is either:
#   - a predicate (Any) -> bool  — returning False means "invalid"
#   - a callable that raises on invalid input
Verifier = Callable[[Any], Any]

# A test takes the current callable being repaired and raises on failure.
Test = Callable[[Callable[..., Any]], Any]


def check_verifier(
    value: Any,
    verify: Verifier | None,
    inputs: dict[str, Any] | None = None,
) -> Failure | None:
    """Check `verify(value)`. Returns a Failure if invalid, else None."""
    if verify is None:
        return None

    ctx = dict(inputs or {})
    ctx["result"] = _truncate_repr(value)

    try:
        ok = verify(value)
    except Exception as exc:
        return Failure(
            kind="verifier",
            error_type=type(exc).__name__,
            message=f"verifier {_name(verify)} raised: {exc}",
            traceback="".join(tb.format_exception(type(exc), exc, exc.__traceback__)),
            inputs=ctx,
        )

    # Predicate-style: a non-exception False value indicates rejection.
    if ok is False:
        return Failure(
            kind="verifier",
            error_type="VerificationRejected",
            message=f"verifier {_name(verify)} returned False for result {ctx['result']}",
            traceback=None,
            inputs=ctx,
        )

    return None


def check_tests(
    func: Callable[..., Any],
    tests: list[Test] | None,
) -> Failure | None:
    """Run each test against `func`. Returns the first failing test as a Failure."""
    if not tests:
        return None

    for test in tests:
        try:
            test(func)
        except Exception as exc:
            return Failure(
                kind="test",
                error_type=type(exc).__name__,
                message=f"test '{_name(test)}' failed: {exc}",
                traceback="".join(
                    tb.format_exception(type(exc), exc, exc.__traceback__)
                ),
                inputs={"test_name": _name(test)},
            )

    return None


def _name(obj: Any) -> str:
    return getattr(obj, "__name__", None) or getattr(obj, "__qualname__", None) or repr(obj)


def _truncate_repr(value: Any, limit: int = 500) -> str:
    r = repr(value)
    return r if len(r) <= limit else r[:limit] + "... [truncated]"
