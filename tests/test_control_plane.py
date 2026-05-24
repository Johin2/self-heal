"""Tests for ControlPlaneClient.

Mocks the underlying httpx.Client.post so no network calls happen.
Covers wire format, batching, idempotent run_key per repair sequence,
non-retryable rejection (4xx), and graceful close.
"""

from __future__ import annotations

import threading
from typing import Any
from unittest.mock import MagicMock

import pytest

from self_heal.control_plane import ControlPlaneClient, _run_key_var
from self_heal.events import RepairEvent
from self_heal.types import Failure


@pytest.fixture(autouse=True)
def _reset_run_key():
    _run_key_var.set(None)
    yield
    _run_key_var.set(None)


def _fake_response(status_code: int = 202, text: str = "{}"):
    r = MagicMock()
    r.status_code = status_code
    r.text = text
    r.json = MagicMock(return_value={})
    return r


def _recorder(sink: list[dict]) -> MagicMock:
    """A MagicMock that records JSON bodies into `sink` and returns 202."""

    def _post(url, headers=None, json=None):  # noqa: ARG001
        sink.append(json)
        return _fake_response()

    return MagicMock(side_effect=_post)


def _make_client(post_mock: MagicMock | None = None, **kwargs: Any) -> ControlPlaneClient:
    cp = ControlPlaneClient(api_key="shc_live_test", **kwargs)
    if post_mock is not None:
        cp._client = MagicMock()
        cp._client.post = post_mock
    return cp


def test_for_function_tags_events_and_shares_run_key_within_a_run():
    posts: list[dict] = []

    def fake_post(url, headers, json):
        posts.append(json)
        return _fake_response()

    cp = _make_client(MagicMock(side_effect=fake_post), batch_size=10, flush_interval=0.05)
    try:
        cb = cp.for_function("billing.compute_total", "billing")

        cb(RepairEvent(type="attempt_start", attempt_number=1))
        cb(RepairEvent(type="attempt_failed", attempt_number=1, error="boom"))
        cb(RepairEvent(type="repair_succeeded", attempt_number=2, proposed_source="def f(): return 1"))

        assert cp.flush(timeout=2.0)
    finally:
        cp.close()

    flat_events = [e for batch in posts for e in batch["events"]]
    assert len(flat_events) == 3
    run_keys = {e["run_key"] for e in flat_events}
    assert len(run_keys) == 1, "all events in one run share a run_key"
    fns = {e["function_name"] for e in flat_events}
    assert fns == {"billing.compute_total"}
    assert flat_events[2]["payload"]["proposed_source"] == "def f(): return 1"


def test_run_key_resets_after_terminal_event():
    posts: list[dict] = []
    cp = _make_client(_recorder(posts), flush_interval=0.05)
    try:
        cb = cp.for_function("svc.fn")

        cb(RepairEvent(type="attempt_start", attempt_number=1))
        cb(RepairEvent(type="repair_succeeded", attempt_number=1))
        cb(RepairEvent(type="attempt_start", attempt_number=1))
        cb(RepairEvent(type="repair_exhausted", attempt_number=3, error="gave up"))

        assert cp.flush(timeout=2.0)
    finally:
        cp.close()

    flat = [e for batch in posts for e in batch["events"]]
    assert len(flat) == 4
    run_a = {flat[0]["run_key"], flat[1]["run_key"]}
    run_b = {flat[2]["run_key"], flat[3]["run_key"]}
    assert len(run_a) == 1 and len(run_b) == 1
    assert run_a != run_b


def test_failure_is_serialized_into_payload():
    posts: list[dict] = []
    cp = _make_client(
        _recorder(posts),
        flush_interval=0.05,
    )
    try:
        cb = cp.for_function("svc.fn")
        cb(
            RepairEvent(
                type="attempt_failed",
                attempt_number=1,
                failure=Failure(
                    kind="exception",
                    error_type="ZeroDivisionError",
                    message="division by zero",
                ),
            )
        )
        assert cp.flush(timeout=2.0)
    finally:
        cp.close()

    flat = [e for batch in posts for e in batch["events"]]
    assert flat[0]["payload"]["failure"]["error_type"] == "ZeroDivisionError"
    assert flat[0]["payload"]["failure"]["kind"] == "exception"


def test_4xx_is_dropped_without_retry():
    post = MagicMock(return_value=_fake_response(status_code=401, text='{"detail":"bad key"}'))
    cp = _make_client(post, flush_interval=0.05, max_retries=5)
    try:
        cp.for_function("svc.fn")(RepairEvent(type="attempt_start", attempt_number=1))
        assert cp.flush(timeout=2.0)
    finally:
        cp.close()
    assert post.call_count == 1, "4xx must not retry"


def test_5xx_retries_then_gives_up():
    post = MagicMock(return_value=_fake_response(status_code=500))
    cp = _make_client(post, flush_interval=0.05, max_retries=3, batch_size=1)
    try:
        cp.for_function("svc.fn")(RepairEvent(type="attempt_start", attempt_number=1))
        assert cp.flush(timeout=10.0)
    finally:
        cp.close()
    assert post.call_count == 3


def test_close_is_idempotent_and_flushes_remaining():
    posts: list[dict] = []
    cp = _make_client(
        _recorder(posts),
        flush_interval=60.0,
    )
    cp.for_function("svc.fn")(RepairEvent(type="attempt_start", attempt_number=1))
    cp.close()
    cp.close()  # second call must not raise
    assert any(posts), "events buffered before close should still be sent"


def test_two_threads_get_independent_run_keys():
    """ContextVar isolation per thread."""
    posts: list[dict] = []
    cp = _make_client(
        _recorder(posts),
        flush_interval=0.05,
    )
    cb = cp.for_function("svc.fn")

    def worker():
        cb(RepairEvent(type="attempt_start", attempt_number=1))
        cb(RepairEvent(type="repair_succeeded", attempt_number=1))

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    cp.flush(timeout=2.0)
    cp.close()

    flat = [e for batch in posts for e in batch["events"]]
    assert len(flat) == 6
    run_keys = {e["run_key"] for e in flat}
    assert len(run_keys) == 3, "each thread should produce its own run_key"
