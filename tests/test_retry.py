"""Tests for retry-with-backoff on transient proposer errors (issue #32).

All tests that involve actual delays use base_delay=0.0 so asyncio.sleep(0)
and time.sleep(0) are called, which are effectively instant.  Tests that
validate delay *values* patch the sleep functions.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from self_heal import RepairEvent, RepairLoop, RetryConfig
from self_heal.retry import _is_transient, awith_retry, with_retry

# _is_transient classification


def test_is_transient_429_in_message():
    assert _is_transient(Exception("HTTP 429 Too Many Requests"))


def test_is_transient_503_in_message():
    assert _is_transient(Exception("503 Service Unavailable"))


def test_is_transient_502_in_message():
    assert _is_transient(Exception("502 Bad Gateway"))


def test_is_transient_timeout_phrase():
    assert _is_transient(Exception("connection timeout after 30s"))


def test_is_transient_rate_limit_phrase():
    assert _is_transient(Exception("rate limit exceeded, retry after 60s"))


def test_is_transient_by_exception_class_name_rate_limit():
    class RateLimitError(Exception):
        pass

    assert _is_transient(RateLimitError("you hit the rate limit"))


def test_is_transient_by_exception_class_name_timeout():
    class ConnectTimeout(Exception):
        pass

    assert _is_transient(ConnectTimeout("connection timed out"))


def test_is_transient_by_exception_class_name_api_timeout():
    class APITimeoutError(Exception):
        pass

    assert _is_transient(APITimeoutError("request timed out"))


def test_not_transient_401():
    assert not _is_transient(Exception("401 Unauthorized: invalid API key"))


def test_not_transient_400():
    assert not _is_transient(Exception("400 Bad Request: missing required field"))


def test_not_transient_generic_value_error():
    assert not _is_transient(ValueError("wrong type provided"))


def test_not_transient_generic_runtime_error():
    assert not _is_transient(RuntimeError("something unexpected happened"))


# with_retry unit tests


def test_with_retry_returns_immediately_on_success():
    result = with_retry(lambda: "ok", RetryConfig(max_retries=3))
    assert result == "ok"


def test_with_retry_retries_transient_and_succeeds():
    calls: list[int] = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise Exception("429 rate limit exceeded")
        return "success"

    with patch("self_heal.retry.time.sleep"):
        result = with_retry(fn, RetryConfig(max_retries=3, base_delay=1.0))

    assert result == "success"
    assert len(calls) == 3


def test_with_retry_does_not_retry_non_transient():
    calls: list[int] = []

    def fn():
        calls.append(1)
        raise ValueError("not a transient error")

    with pytest.raises(ValueError, match="not a transient error"):
        with_retry(fn, RetryConfig(max_retries=3))

    assert len(calls) == 1


def test_with_retry_raises_original_after_exhausting_retries():
    calls: list[int] = []

    def fn():
        calls.append(1)
        raise Exception("503 temporarily unavailable")

    with patch("self_heal.retry.time.sleep"), pytest.raises(Exception, match="503"):
        with_retry(fn, RetryConfig(max_retries=2, base_delay=1.0))

    assert len(calls) == 3  # 1 initial + 2 retries


def test_with_retry_invokes_on_retry_callback():
    retry_calls: list[tuple[int, float]] = []
    calls: list[int] = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise Exception("429")
        return "ok"

    with patch("self_heal.retry.time.sleep"):
        with_retry(
            fn,
            RetryConfig(max_retries=3, base_delay=1.0, backoff_factor=2.0, jitter=0),
            on_retry=lambda n, d, e: retry_calls.append((n, d)),
        )

    assert retry_calls == [(1, 1.0), (2, 2.0)]


def test_with_retry_applies_jitter():
    delays: list[float] = []

    def fn():
        if len(delays) < 4:
            raise Exception("429")
        return "ok"

    with patch("self_heal.retry.time.sleep"):
        with_retry(
            fn,
            RetryConfig(max_retries=5, base_delay=1.0, backoff_factor=1.0, jitter=0.25),
            on_retry=lambda n, d, e: delays.append(d),
        )

    assert all(0.75 <= d <= 1.25 for d in delays)
    assert len(set(delays)) > 1


def test_with_retry_caps_delay_at_max_delay():
    delays: list[float] = []

    def fn():
        raise Exception("429")

    with patch("self_heal.retry.time.sleep"), pytest.raises(Exception, match="429"):
        with_retry(
            fn,
            RetryConfig(
                max_retries=5,
                base_delay=10.0,
                backoff_factor=10.0,
                max_delay=30.0,
                jitter=0,
            ),
            on_retry=lambda n, d, e: delays.append(d),
        )

    assert len(delays) == 5
    assert all(d <= 30.0 for d in delays)


def test_jitter_applied_after_cap_spreads_saturated_backoff():
    """When backoff saturates at max_delay, jitter still spreads delays."""
    delays: list[float] = []

    def fn():
        raise Exception("429")

    with patch("self_heal.retry.time.sleep"), pytest.raises(Exception, match="429"):
        with_retry(
            fn,
            RetryConfig(
                max_retries=10,
                base_delay=1000.0,  # saturates immediately
                backoff_factor=2.0,
                max_delay=30.0,
                jitter=0.25,
            ),
            on_retry=lambda n, d, e: delays.append(d),
        )

    assert all(22.5 <= d <= 37.5 for d in delays)
    assert len(set(delays)) > 1  # jitter actually varies them


# awith_retry unit tests


def test_awith_retry_returns_immediately_on_success():
    async def afn():
        return "async ok"

    result = asyncio.run(awith_retry(afn, RetryConfig(max_retries=3, base_delay=0.0)))
    assert result == "async ok"


def test_awith_retry_retries_transient_and_succeeds():
    calls: list[int] = []

    async def afn():
        calls.append(1)
        if len(calls) < 2:
            raise Exception("429 rate limit")
        return "fixed"

    result = asyncio.run(awith_retry(afn, RetryConfig(max_retries=3, base_delay=0.0)))
    assert result == "fixed"
    assert len(calls) == 2


def test_awith_retry_does_not_retry_non_transient():
    calls: list[int] = []

    async def afn():
        calls.append(1)
        raise TypeError("bad type")

    with pytest.raises(TypeError):
        asyncio.run(awith_retry(afn, RetryConfig(max_retries=3, base_delay=0.0)))

    assert len(calls) == 1


def test_awith_retry_raises_after_exhausting_retries():
    calls: list[int] = []

    async def afn():
        calls.append(1)
        raise Exception("503")

    with pytest.raises(Exception, match="503"):
        asyncio.run(awith_retry(afn, RetryConfig(max_retries=2, base_delay=0.0)))

    assert len(calls) == 3


# RepairLoop integration: sync


def test_repair_loop_retries_proposer_on_429():
    calls: list[int] = []

    class FlakyProposer:
        def propose(self, system, user):
            calls.append(1)
            if len(calls) == 1:
                raise Exception("429 Too Many Requests")
            return "def broken(x):\n    return x * 2\n"

    loop = RepairLoop(
        max_attempts=2,
        proposer=FlakyProposer(),
        retry_config=RetryConfig(max_retries=3, base_delay=0.0),
    )

    def broken(x):
        return None

    result = loop.run(broken, args=(5,), verify=lambda v: v == 10)
    assert result.succeeded
    assert len(calls) == 2  # 1 transient failure + 1 successful retry


def test_repair_loop_retries_proposer_on_503():
    calls: list[int] = []

    class FlakyProposer:
        def propose(self, system, user):
            calls.append(1)
            if len(calls) < 3:
                raise Exception("503 Service Unavailable")
            return "def broken(x):\n    return x * 2\n"

    loop = RepairLoop(
        max_attempts=2,
        proposer=FlakyProposer(),
        retry_config=RetryConfig(max_retries=3, base_delay=0.0),
    )

    def broken(x):
        return None

    result = loop.run(broken, args=(5,), verify=lambda v: v == 10)
    assert result.succeeded
    assert len(calls) == 3


def test_repair_loop_no_retry_on_auth_error():
    calls: list[int] = []

    class AuthErrorProposer:
        def propose(self, system, user):
            calls.append(1)
            raise Exception("401 Unauthorized: invalid API key")

    loop = RepairLoop(
        max_attempts=2,
        proposer=AuthErrorProposer(),
        retry_config=RetryConfig(max_retries=3, base_delay=0.0),
    )

    def broken(x):
        return None

    with pytest.raises(Exception, match="401"):
        loop.run(broken, args=(5,), verify=lambda v: v == 10)

    assert len(calls) == 1  # not retried


def test_repair_loop_exhausted_retries_propagates_exception():
    class AlwaysRateLimited:
        def propose(self, system, user):
            raise Exception("429 rate limit")

    loop = RepairLoop(
        max_attempts=2,
        proposer=AlwaysRateLimited(),
        retry_config=RetryConfig(max_retries=2, base_delay=0.0),
    )

    def broken(x):
        return None

    with pytest.raises(Exception, match="429"):
        loop.run(broken, args=(5,), verify=lambda v: v == 10)


def test_repair_loop_emits_retry_events():
    calls: list[int] = []
    events: list[RepairEvent] = []

    class FlakyProposer:
        def propose(self, system, user):
            calls.append(1)
            if len(calls) < 3:
                raise Exception("503 Service Unavailable")
            return "def broken(x):\n    return x * 2\n"

    loop = RepairLoop(
        max_attempts=2,
        proposer=FlakyProposer(),
        retry_config=RetryConfig(max_retries=3, base_delay=0.0),
        on_event=lambda e: events.append(e),
    )

    def broken(x):
        return None

    result = loop.run(broken, args=(5,), verify=lambda v: v == 10)
    assert result.succeeded

    retry_events = [e for e in events if e.type == "transient_retry"]
    assert len(retry_events) == 2
    assert retry_events[0].retry_attempt == 1
    assert retry_events[1].retry_attempt == 2
    assert retry_events[0].retry_delay is not None
    assert retry_events[0].error is not None


def test_repair_loop_without_retry_config_propagates_transient():
    class TransientProposer:
        def propose(self, system, user):
            raise Exception("429 rate limit — no retry configured")

    loop = RepairLoop(
        max_attempts=2,
        proposer=TransientProposer(),
        # no retry_config
    )

    def broken(x):
        return None

    with pytest.raises(Exception, match="429"):
        loop.run(broken, args=(5,), verify=lambda v: v == 10)


# RepairLoop integration: async


def test_repair_loop_async_retry_on_503():
    calls: list[int] = []

    class FlakyProposer:
        def propose(self, system, user):
            calls.append(1)
            if len(calls) == 1:
                raise Exception("503")
            return "def broken(x):\n    return x * 2\n"

    loop = RepairLoop(
        max_attempts=2,
        proposer=FlakyProposer(),
        retry_config=RetryConfig(max_retries=3, base_delay=0.0),
    )

    def broken(x):
        return None

    result = asyncio.run(loop.arun(broken, args=(5,), verify=lambda v: v == 10))
    assert result.succeeded
    assert len(calls) == 2


def test_repair_loop_async_emits_retry_events():
    calls: list[int] = []
    events: list[RepairEvent] = []

    class FlakyProposer:
        def propose(self, system, user):
            calls.append(1)
            if len(calls) < 2:
                raise Exception("429")
            return "def broken(x):\n    return x * 2\n"

    loop = RepairLoop(
        max_attempts=2,
        proposer=FlakyProposer(),
        retry_config=RetryConfig(max_retries=3, base_delay=0.0),
        on_event=lambda e: events.append(e),
    )

    def broken(x):
        return None

    result = asyncio.run(loop.arun(broken, args=(5,), verify=lambda v: v == 10))
    assert result.succeeded

    retry_events = [e for e in events if e.type == "transient_retry"]
    assert len(retry_events) == 1
    assert retry_events[0].retry_attempt == 1


# Public API


def test_retry_config_importable_from_self_heal():
    from self_heal import RetryConfig as RC

    cfg = RC(max_retries=5, base_delay=0.5)
    assert cfg.max_retries == 5
    assert cfg.base_delay == 0.5
    assert cfg.max_delay == 30.0  # default
    assert cfg.backoff_factor == 2.0  # default


def test_retry_config_in_all():
    import self_heal

    assert "RetryConfig" in self_heal.__all__


# False-positive guards (issue: bare substring match would over-trigger)


def test_not_transient_status_code_substring_in_value():
    """ValueError("field value 5031 out of range") must NOT be transient."""
    assert not _is_transient(ValueError("field value 5031 out of range"))


def test_not_transient_status_code_inside_larger_number():
    assert not _is_transient(Exception("expected 4290 items, got 1"))


def test_not_transient_timeout_must_be_positive_message():
    """RuntimeError mentioning timeout config — not the network condition."""
    assert not _is_transient(RuntimeError("timeout must be > 0"))


# MRO walk: subclasses of known SDK errors


def test_is_transient_subclass_of_rate_limit_error():
    class RateLimitError(Exception):
        pass

    class BillingRateLimitError(RateLimitError):
        pass

    assert _is_transient(BillingRateLimitError("billing"))


# status_code attribute


def test_is_transient_via_status_code_attribute():
    class APIError(Exception):
        def __init__(self, msg, status_code):
            super().__init__(msg)
            self.status_code = status_code

    assert _is_transient(APIError("server is having a moment", status_code=503))
    assert _is_transient(APIError("slow down", status_code=429))
    assert not _is_transient(APIError("bad key", status_code=401))


def test_is_transient_via_response_status_code():
    class _Resp:
        def __init__(self, code):
            self.status_code = code

    class HTTPError(Exception):
        def __init__(self, msg, response):
            super().__init__(msg)
            self.response = response

    assert _is_transient(HTTPError("err", _Resp(503)))
    assert not _is_transient(HTTPError("err", _Resp(400)))


# New phrases


def test_is_transient_timed_out_phrase():
    assert _is_transient(Exception("Read timed out."))


def test_is_transient_connection_reset_phrase():
    assert _is_transient(OSError("connection reset by peer"))


def test_is_transient_connection_refused_phrase():
    assert _is_transient(OSError("connection refused"))


# Retry-After honoring


def test_retry_after_attribute_overrides_computed_backoff():
    class RateLimitError(Exception):
        def __init__(self, msg, retry_after):
            super().__init__(msg)
            self.retry_after = retry_after

    delays: list[float] = []
    calls: list[int] = []

    def fn():
        calls.append(1)
        if len(calls) < 2:
            raise RateLimitError("slow down", retry_after=7.5)
        return "ok"

    with patch("self_heal.retry.time.sleep"):
        with_retry(
            fn,
            RetryConfig(max_retries=3, base_delay=1.0, jitter=0),
            on_retry=lambda n, d, e: delays.append(d),
        )

    assert delays == [7.5]


def test_retry_after_response_header_overrides_backoff():
    class _Headers(dict):
        pass

    class _Resp:
        def __init__(self, headers):
            self.headers = headers
            self.status_code = 429

    class HTTPError(Exception):
        def __init__(self, msg, response):
            super().__init__(msg)
            self.response = response

    delays: list[float] = []
    calls: list[int] = []

    def fn():
        calls.append(1)
        if len(calls) < 2:
            raise HTTPError("429", _Resp(_Headers({"retry-after": "12"})))
        return "ok"

    with patch("self_heal.retry.time.sleep"):
        with_retry(
            fn,
            RetryConfig(max_retries=3, base_delay=1.0, jitter=0),
            on_retry=lambda n, d, e: delays.append(d),
        )

    assert delays == [12.0]


def test_retry_after_capped_at_max_delay():
    class RateLimitError(Exception):
        def __init__(self, msg, retry_after):
            super().__init__(msg)
            self.retry_after = retry_after

    delays: list[float] = []
    calls: list[int] = []

    def fn():
        calls.append(1)
        if len(calls) < 2:
            raise RateLimitError("slow down", retry_after=600)
        return "ok"

    with patch("self_heal.retry.time.sleep"):
        with_retry(
            fn,
            RetryConfig(max_retries=3, base_delay=1.0, max_delay=30.0, jitter=0),
            on_retry=lambda n, d, e: delays.append(d),
        )

    assert delays == [30.0]


def test_retry_after_can_be_disabled():
    class RateLimitError(Exception):
        def __init__(self, msg, retry_after):
            super().__init__(msg)
            self.retry_after = retry_after

    delays: list[float] = []
    calls: list[int] = []

    def fn():
        calls.append(1)
        if len(calls) < 2:
            raise RateLimitError("slow down", retry_after=99)
        return "ok"

    with patch("self_heal.retry.time.sleep"):
        with_retry(
            fn,
            RetryConfig(
                max_retries=3, base_delay=1.0, jitter=0, respect_retry_after=False
            ),
            on_retry=lambda n, d, e: delays.append(d),
        )

    assert delays == [1.0]  # computed backoff, not the 99s hint


def test_malformed_retry_after_falls_back_to_backoff():
    class RateLimitError(Exception):
        def __init__(self, msg, retry_after):
            super().__init__(msg)
            self.retry_after = retry_after

    delays: list[float] = []
    calls: list[int] = []

    def fn():
        calls.append(1)
        if len(calls) < 2:
            raise RateLimitError("slow down", retry_after="not-a-number")
        return "ok"

    with patch("self_heal.retry.time.sleep"):
        with_retry(
            fn,
            RetryConfig(max_retries=3, base_delay=2.0, jitter=0),
            on_retry=lambda n, d, e: delays.append(d),
        )

    assert delays == [2.0]
