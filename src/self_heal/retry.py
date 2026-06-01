#Retry helpers for transient LLM provider errors (429, 503, timeouts)

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeVar

T = TypeVar("T")

_TRANSIENT_STATUS_CODES = frozenset({"429", "502", "503", "504"})
_TRANSIENT_CLASS_NAMES = frozenset({
    "RateLimitError",
    "APITimeoutError",
    "APIConnectionError",
    "ServiceUnavailableError",
    "Timeout",
    "TimeoutError",
    "TimeoutException",
    "ConnectTimeout",
    "ReadTimeout",
    "RemoteProtocolError",
})
_TRANSIENT_PHRASES = ("rate limit", "too many requests", "timeout", "service unavailable")


@dataclass
class RetryConfig:
    """Policy for retrying transient LLM provider errors.

    Args:
        max_retries: Maximum number of retries after the initial attempt.
        base_delay: Initial wait in seconds before the first retry.
        max_delay: Upper cap on inter-retry delay (seconds).
        backoff_factor: Multiplier applied to the delay after each retry.
        jitter: Fractional jitter applied to each delay (0.25 = ±25%).
            Set to 0 to disable.
        transient_status_codes: Optional custom set of HTTP status codes
            (as strings) that should be treated as transient.  When
            ``None`` (the default) the built-in set is used.
        transient_class_names: Optional custom set of exception class names
            that should be treated as transient.  When ``None`` the
            built-in set is used.
        transient_phrases: Optional custom tuple of substrings matched
            (case-insensitive) against the exception message.  When
            ``None`` the built-in phrases are used.
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    backoff_factor: float = 2.0
    jitter: float = 0.25
    transient_status_codes: frozenset[str] | None = None
    transient_class_names: frozenset[str] | None = None
    transient_phrases: tuple[str, ...] | None = None


def _compute_delay(config: RetryConfig, attempt: int) -> float:
    """Exponential backoff with bounded random jitter, capped at max_delay."""
    raw = config.base_delay * config.backoff_factor**attempt
    if config.jitter > 0:
        raw *= 1.0 + random.uniform(-config.jitter, config.jitter)
    return min(max(raw, 0.0), config.max_delay)


def _is_transient(exc: BaseException, config: RetryConfig | None = None) -> bool:
    """Return True if *exc* looks like a transient provider error worth retrying.

    When *config* is None, the built-in default matcher sets are used.
    """
    if config is None:
        config = RetryConfig()

    class_names = (
        config.transient_class_names
        if config.transient_class_names is not None
        else _TRANSIENT_CLASS_NAMES
    )
    if type(exc).__name__ in class_names:
        return True

    msg = str(exc).lower()

    status_codes = (
        config.transient_status_codes
        if config.transient_status_codes is not None
        else _TRANSIENT_STATUS_CODES
    )
    if any(code in msg for code in status_codes):
        return True

    phrases = (
        config.transient_phrases
        if config.transient_phrases is not None
        else _TRANSIENT_PHRASES
    )
    return any(phrase in msg for phrase in phrases)


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
            if not _is_transient(exc, config) or attempt == config.max_retries:
                raise
            delay = _compute_delay(config, attempt)
            if on_retry is not None:
                on_retry(attempt + 1, delay, exc)
            time.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


async def awith_retry(
    afn: Callable[[], Awaitable[T]],
    config: RetryConfig,
    on_retry: Callable[[int, float, BaseException], None] | None = None,
) -> T:
    """Async variant of :func:`with_retry`.

    Args:
        afn: Zero-argument async callable (or callable returning an awaitable).
        config: Retry policy.
        on_retry: Optional callback invoked before each retry.
    """
    for attempt in range(config.max_retries + 1):
        try:
            return await afn()
        except Exception as exc:
            if not _is_transient(exc, config) or attempt == config.max_retries:
                raise
            delay = _compute_delay(config, attempt)
            if on_retry is not None:
                on_retry(attempt + 1, delay, exc)
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
