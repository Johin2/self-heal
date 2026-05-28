"""Retry helpers for transient LLM provider errors (429, 503, timeouts)."""

from __future__ import annotations

import asyncio
import random
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

# Anchored on word boundaries so "5031" in a value-error message does not match.
_STATUS_CODE_RE = re.compile(r"\b(429|502|503|504)\b")

_TRANSIENT_CLASS_NAMES = frozenset(
    {
        "RateLimitError",
        "APITimeoutError",
        "APIConnectionError",
        "ServiceUnavailableError",
        "InternalServerError",
        "Timeout",
        "TimeoutError",
        "TimeoutException",
        "ConnectTimeout",
        "ReadTimeout",
        "ReadTimeoutError",
        "ConnectionResetError",
        "RemoteProtocolError",
    }
)

_TRANSIENT_PHRASES = (
    "rate limit",
    "too many requests",
    "timed out",
    "request timeout",
    "connection timeout",
    "read timeout",
    "service unavailable",
    "connection reset",
    "connection refused",
    "temporarily unavailable",
)


@dataclass
class RetryConfig:
    """Policy for retrying transient LLM provider errors.

    Args:
        max_retries: Maximum number of retries after the initial attempt.
        base_delay: Initial wait in seconds before the first retry.
        max_delay: Upper cap on inter-retry delay (seconds).
        backoff_factor: Multiplier applied to the delay after each retry.
        jitter: Fractional jitter applied to each delay (0.25 = ±25%).
            Applied after the max_delay cap so saturated backoff still
            spreads concurrent clients. Set to 0 to disable.
        respect_retry_after: When True, honor a numeric ``Retry-After``
            value found on the exception (``retry_after`` attribute or
            ``response.headers['Retry-After']``) instead of the computed
            backoff. The value is still capped at ``max_delay``.
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    backoff_factor: float = 2.0
    jitter: float = 0.25
    respect_retry_after: bool = True


def _is_transient(exc: BaseException) -> bool:
    """Return True if *exc* looks like a transient provider error worth retrying.

    Classifies by, in order:

    1. Class name walking the full MRO (so subclasses of known SDK errors
       like ``BillingRateLimitError(RateLimitError)`` are caught).
    2. Structured ``status_code`` attribute on the exception or its
       ``response`` (httpx / openai / anthropic style).
    3. Word-boundary match on common transient HTTP status codes in the
       message text.
    4. Substring match on known transient phrases.
    """
    for cls in type(exc).__mro__:
        if cls.__name__ in _TRANSIENT_CLASS_NAMES:
            return True

    code = _extract_status_code(exc)
    if code in (429, 502, 503, 504):
        return True

    msg = str(exc).lower()
    if _STATUS_CODE_RE.search(msg):
        return True
    return any(phrase in msg for phrase in _TRANSIENT_PHRASES)


def _extract_status_code(exc: BaseException) -> int | None:
    """Pull an HTTP status code off the exception when SDKs expose one."""
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code
    response = getattr(exc, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            return code
    return None


def _extract_retry_after(exc: BaseException) -> float | None:
    """Pull a Retry-After value (seconds) off the exception when present."""
    raw = getattr(exc, "retry_after", None)
    if raw is None:
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None) if response is not None else None
        if headers is not None:
            try:
                raw = headers.get("retry-after") or headers.get("Retry-After")
            except Exception:
                raw = None
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return value


def _compute_delay(
    config: RetryConfig, attempt: int, exc: BaseException | None = None
) -> float:
    """Exponential backoff with jitter, capped at max_delay.

    The cap is applied *before* jitter so saturated backoff still spreads
    concurrent clients instead of all clamping to exactly max_delay.
    A ``Retry-After`` value on *exc* (when ``respect_retry_after``) wins
    over the computed backoff but is still capped.
    """
    if exc is not None and config.respect_retry_after:
        retry_after = _extract_retry_after(exc)
        if retry_after is not None:
            return min(retry_after, config.max_delay)

    raw = config.base_delay * config.backoff_factor**attempt
    delay = min(raw, config.max_delay)
    if config.jitter > 0:
        delay *= 1.0 + random.uniform(-config.jitter, config.jitter)
    return max(delay, 0.0)


def with_retry(
    fn: Callable[[], T],
    config: RetryConfig,
    on_retry: Callable[[int, float, BaseException], None] | None = None,
) -> T:
    """Call *fn()* and retry on transient errors using exponential backoff.

    Args:
        fn: Zero-argument callable to invoke.
        config: Retry policy.
        on_retry: Optional callback invoked before each retry with
            ``(retry_number, delay_seconds, exception)``.

    Raises:
        The original exception if it is not transient or retries are exhausted.
    """
    for attempt in range(config.max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            if not _is_transient(exc) or attempt == config.max_retries:
                raise
            delay = _compute_delay(config, attempt, exc)
            if on_retry is not None:
                on_retry(attempt + 1, delay, exc)
            time.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


async def awith_retry(
    afn: Callable[[], Awaitable[T]],
    config: RetryConfig,
    on_retry: Callable[[int, float, BaseException], None] | None = None,
) -> T:
    """Async variant of :func:`with_retry`."""
    for attempt in range(config.max_retries + 1):
        try:
            return await afn()
        except Exception as exc:
            if not _is_transient(exc) or attempt == config.max_retries:
                raise
            delay = _compute_delay(config, attempt, exc)
            if on_retry is not None:
                on_retry(attempt + 1, delay, exc)
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
