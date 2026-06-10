#Retry helpers for transient LLM provider errors (429, 503, timeouts)

from __future__ import annotations

import asyncio
import random
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

_TRANSIENT_STATUS_CODES = {"429", "502", "503", "504"}
_TRANSIENT_CLASS_NAMES = {
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
}
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
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    backoff_factor: float = 2.0
    jitter: float = 0.25


def _compute_delay(config: RetryConfig, attempt: int) -> float:
    """Exponential backoff with bounded random jitter, capped at max_delay."""
    raw = config.base_delay * config.backoff_factor**attempt
    if config.jitter > 0:
        raw *= 1.0 + random.uniform(-config.jitter, config.jitter)
    return min(max(raw, 0.0), config.max_delay)


def _is_transient(exc: BaseException) -> bool:
    """Return True if *exc* looks like a transient provider error worth retrying."""
    if type(exc).__name__ in _TRANSIENT_CLASS_NAMES:
        return True
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    msg = str(exc).lower()
    if re.search(r"\b(429|502|503|504)\b", msg):
        return True
    return any(phrase in msg for phrase in _TRANSIENT_PHRASES)


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
            if not _is_transient(exc) or attempt == config.max_retries:
                raise
            delay = _compute_delay(config, attempt)
            if on_retry is not None:
                on_retry(attempt + 1, delay, exc)
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
