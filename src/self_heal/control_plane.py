"""ControlPlaneClient — ships RepairEvents to the hosted control plane.

Usage:
    from self_heal import repair
    from self_heal.control_plane import ControlPlaneClient

    cp = ControlPlaneClient(api_key="shc_live_...")

    @repair(on_event=cp.for_function("billing.compute_total"))
    def compute_total(...): ...

One client per process, one bound callback per repaired function. Events
are buffered in memory and flushed by a background thread every
`flush_interval` seconds (or sooner if the buffer fills). The client
NEVER raises into the repair loop; transport errors are logged and
dropped.
"""

from __future__ import annotations

import atexit
import contextlib
import dataclasses
import logging
import threading
import time
import uuid
from collections import deque
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

try:
    import httpx
except ImportError as _err:  # pragma: no cover
    raise ImportError(
        "ControlPlaneClient requires httpx. Install with: pip install httpx"
    ) from _err

from self_heal.events import RepairEvent

_log = logging.getLogger("self_heal.control_plane")

_TERMINAL_TYPES = frozenset({"repair_succeeded", "repair_exhausted"})

_run_key_var: ContextVar[str | None] = ContextVar("_shc_cp_run_key", default=None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event_to_payload(
    event: RepairEvent, function_name: str, module_name: str | None
) -> dict[str, Any]:
    """Translate an OSS RepairEvent into the control-plane wire format."""
    run_key = _run_key_var.get()
    if run_key is None:
        run_key = uuid.uuid4().hex
        _run_key_var.set(run_key)

    failure_payload: dict[str, Any] | None = None
    if event.failure is not None:
        try:
            failure_payload = event.failure.model_dump(mode="json")
        except AttributeError:  # not a pydantic model
            failure_payload = dataclasses.asdict(event.failure)  # type: ignore[arg-type]

    payload: dict[str, Any] = {}
    if failure_payload is not None:
        payload["failure"] = failure_payload
    if event.proposed_source is not None:
        payload["proposed_source"] = event.proposed_source
    if event.error is not None:
        payload["error"] = event.error
    if event.delta is not None:
        payload["delta"] = event.delta
    if event.extra:
        payload["extra"] = event.extra

    wire = {
        "event_id": uuid.uuid4().hex,
        "ts": _now_iso(),
        "run_key": run_key,
        "type": event.type,
        "function_name": function_name,
        "module_name": module_name,
        "attempt_number": event.attempt_number,
        "payload": payload,
    }

    if event.type in _TERMINAL_TYPES:
        _run_key_var.set(None)

    return wire


class ControlPlaneClient:
    """A buffered, threaded event shipper for self-heal's control plane.

    The client is safe to share across threads and across repaired
    functions. Call `for_function(name)` to get a thin wrapper that
    tags every event with that function's name before queuing it.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://control.self-heal.dev",
        batch_size: int = 50,
        flush_interval: float = 5.0,
        max_buffer: int = 10_000,
        timeout: float = 5.0,
        max_retries: int = 3,
    ):
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._endpoint = base_url.rstrip("/") + "/v1/events"
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._max_buffer = max_buffer
        self._timeout = timeout
        self._max_retries = max_retries

        self._buffer: deque[dict[str, Any]] = deque()
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()

        self._client = httpx.Client(timeout=timeout)
        self._flusher = threading.Thread(
            target=self._run_flusher, name="shc-cp-flusher", daemon=True
        )
        self._flusher.start()
        atexit.register(self.close)

    # -- public surface --------------------------------------------------

    def for_function(
        self, function_name: str, module_name: str | None = None
    ) -> _BoundCallback:
        return _BoundCallback(self, function_name, module_name)

    def __call__(self, event: RepairEvent) -> None:
        """Used when the client is passed directly as `on_event`.

        Function name is extracted from `event.extra` if present;
        otherwise it falls back to `unknown`. Prefer `for_function(...)`
        for explicit attribution.
        """
        function_name = "unknown"
        module_name: str | None = None
        if event.extra:
            function_name = str(event.extra.get("function_name", "unknown"))
            mod = event.extra.get("module_name")
            module_name = str(mod) if mod else None
        self._enqueue(_event_to_payload(event, function_name, module_name))

    def flush(self, timeout: float = 5.0) -> bool:
        """Block until the buffer is empty or `timeout` elapses.

        Returns True if the buffer drained; False otherwise.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._wake.set()
            with self._lock:
                if not self._buffer:
                    return True
            time.sleep(0.05)
        with self._lock:
            return not self._buffer

    def close(self) -> None:
        if self._stop.is_set():
            return
        self._stop.set()
        self._wake.set()
        self.flush(timeout=2.0)
        self._flusher.join(timeout=2.0)
        with contextlib.suppress(Exception):
            self._client.close()

    # -- internals -------------------------------------------------------

    def _enqueue(self, wire: dict[str, Any]) -> None:
        with self._lock:
            if len(self._buffer) >= self._max_buffer:
                # drop oldest to bound memory under sustained outage
                self._buffer.popleft()
                _log.warning("control plane buffer full; dropping oldest event")
            self._buffer.append(wire)
            should_wake = len(self._buffer) >= self._batch_size
        if should_wake:
            self._wake.set()

    def _drain_batch(self) -> list[dict[str, Any]]:
        with self._lock:
            n = min(len(self._buffer), self._batch_size)
            batch = [self._buffer.popleft() for _ in range(n)]
        return batch

    def _requeue_front(self, batch: list[dict[str, Any]]) -> None:
        with self._lock:
            self._buffer.extendleft(reversed(batch))

    def _run_flusher(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(self._flush_interval)
            self._wake.clear()
            while True:
                batch = self._drain_batch()
                if not batch:
                    break
                if not self._post_with_retry(batch):
                    # transport failure: drop the batch rather than
                    # spin forever, but log loudly.
                    _log.error("control plane: gave up on a batch of %d events", len(batch))
                    break

    def _post_with_retry(self, batch: list[dict[str, Any]]) -> bool:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {"events": batch}
        backoff = 0.5
        for attempt in range(self._max_retries):
            try:
                resp = self._client.post(self._endpoint, headers=headers, json=payload)
                if 200 <= resp.status_code < 300:
                    return True
                if resp.status_code in (400, 401, 403, 422):
                    # Non-retryable client error.
                    _log.warning(
                        "control plane rejected batch (%s): %s",
                        resp.status_code,
                        resp.text[:200],
                    )
                    return True  # drop and move on
                _log.warning(
                    "control plane %s on attempt %d", resp.status_code, attempt + 1
                )
            except httpx.HTTPError as e:
                _log.warning("control plane transport error: %s", e)
            time.sleep(backoff)
            backoff = min(backoff * 2, 8.0)
        return False


class _BoundCallback:
    """A function-scoped wrapper that tags every event with a name."""

    __slots__ = ("_client", "_function_name", "_module_name")

    def __init__(
        self,
        client: ControlPlaneClient,
        function_name: str,
        module_name: str | None,
    ):
        self._client = client
        self._function_name = function_name
        self._module_name = module_name

    def __call__(self, event: RepairEvent) -> None:
        self._client._enqueue(
            _event_to_payload(event, self._function_name, self._module_name)
        )
