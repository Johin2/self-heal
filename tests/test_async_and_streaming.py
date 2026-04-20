"""Tests for v0.4 features: native async apropose + streaming propose_chunk."""

from __future__ import annotations

import asyncio

from self_heal import RepairEvent, RepairLoop


class SyncOnlyProposer:
    """Implements `propose` only. arun should fall back to to_thread."""

    def __init__(self, response: str):
        self.response = response
        self.calls = 0

    def propose(self, system: str, user: str) -> str:
        self.calls += 1
        return self.response


class AsyncNativeProposer:
    """Implements both propose and apropose natively."""

    def __init__(self, response: str):
        self.response = response
        self.sync_calls = 0
        self.async_calls = 0

    def propose(self, system: str, user: str) -> str:
        self.sync_calls += 1
        return self.response

    async def apropose(self, system: str, user: str) -> str:
        self.async_calls += 1
        # simulate an await
        await asyncio.sleep(0)
        return self.response


class StreamingProposer:
    """Implements streaming. Yields deltas in chunks."""

    def __init__(self, response: str, chunk_size: int = 4):
        self.response = response
        self.chunk_size = chunk_size
        self.propose_calls = 0

    def propose(self, system: str, user: str) -> str:
        self.propose_calls += 1
        return self.response

    def propose_stream(self, system: str, user: str):
        for i in range(0, len(self.response), self.chunk_size):
            yield self.response[i : i + self.chunk_size]

    async def apropose_stream(self, system: str, user: str):
        for i in range(0, len(self.response), self.chunk_size):
            await asyncio.sleep(0)
            yield self.response[i : i + self.chunk_size]


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


def test_arun_uses_native_apropose_when_present():
    p = AsyncNativeProposer("def f(x):\n    return x * 2\n")
    loop = RepairLoop(max_attempts=2, proposer=p)

    def f(x):
        return None  # verifier will reject

    result = asyncio.run(loop.arun(f, args=(5,), verify=lambda v: v == 10))
    assert result.succeeded
    assert p.async_calls == 1
    assert p.sync_calls == 0  # did NOT go through sync path


def test_arun_falls_back_to_thread_for_sync_only_proposer():
    p = SyncOnlyProposer("def f(x):\n    return x * 2\n")
    loop = RepairLoop(max_attempts=2, proposer=p)

    def f(x):
        return None

    result = asyncio.run(loop.arun(f, args=(5,), verify=lambda v: v == 10))
    assert result.succeeded
    assert p.calls == 1


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


def test_run_emits_propose_chunk_events_when_streaming():
    source = "def square(n):\n    return n * n\n"
    p = StreamingProposer(source, chunk_size=8)

    chunks: list[str] = []

    def watch(event: RepairEvent):
        if event.type == "propose_chunk" and event.delta:
            chunks.append(event.delta)

    loop = RepairLoop(max_attempts=2, proposer=p, on_event=watch)

    def square(n):
        return n + n  # wrong

    result = loop.run(
        square, args=(4,), verify=lambda v: v == 16
    )
    assert result.succeeded
    assert "".join(chunks) == source
    assert len(chunks) > 1  # actually streamed


def test_streaming_not_emitted_without_on_event():
    """If no callback is registered, skip streaming to save overhead."""
    source = "def f(x):\n    return x * 2\n"
    p = StreamingProposer(source, chunk_size=4)
    loop = RepairLoop(max_attempts=2, proposer=p)

    def f(x):
        return None

    result = loop.run(f, args=(5,), verify=lambda v: v == 10)
    assert result.succeeded
    assert p.propose_calls == 1  # used sync propose, not stream


def test_arun_emits_propose_chunk_events_when_streaming():
    source = "def cube(n):\n    return n ** 3\n"
    p = StreamingProposer(source, chunk_size=6)

    chunks: list[str] = []

    def watch(event: RepairEvent):
        if event.type == "propose_chunk" and event.delta:
            chunks.append(event.delta)

    loop = RepairLoop(max_attempts=2, proposer=p, on_event=watch)

    def cube(n):
        return n * 3  # wrong

    result = asyncio.run(
        loop.arun(cube, args=(3,), verify=lambda v: v == 27)
    )
    assert result.succeeded
    assert "".join(chunks) == source


def test_streaming_failure_falls_back_to_propose():
    """If the stream raises, fall back to the sync propose() path."""
    source = "def f(x):\n    return x + 1\n"

    class Broken:
        def __init__(self):
            self.propose_calls = 0

        def propose(self, s, u):
            self.propose_calls += 1
            return source

        def propose_stream(self, s, u):
            raise RuntimeError("stream broken")
            yield  # pragma: no cover (generator marker)

    p = Broken()
    events: list[str] = []
    loop = RepairLoop(
        max_attempts=2, proposer=p, on_event=lambda e: events.append(e.type)
    )

    def f(x):
        return None

    result = loop.run(f, args=(1,), verify=lambda v: v == 2)
    assert result.succeeded
    assert p.propose_calls == 1
    assert "propose_complete" in events


def test_repair_event_has_delta_field():
    e = RepairEvent(type="propose_chunk", delta="hello")
    assert e.delta == "hello"


# ---------------------------------------------------------------------------
# stream_error regression tests
# ---------------------------------------------------------------------------


def test_run_emits_stream_error_with_error_payload():
    """sync path: propose_stream raising must emit stream_error with the
    exception message as the error field, then fall back to propose()."""
    source = "def f(x):\n    return x * 2\n"
    error_message = "network timeout"

    class BrokenStream:
        def __init__(self):
            self.propose_calls = 0

        def propose(self, s, u):
            self.propose_calls += 1
            return source

        def propose_stream(self, s, u):
            raise RuntimeError(error_message)
            yield  # pragma: no cover

    p = BrokenStream()
    events: list[RepairEvent] = []
    loop = RepairLoop(
        max_attempts=2, proposer=p, on_event=lambda e: events.append(e)
    )

    def f(x):
        return None

    result = loop.run(f, args=(5,), verify=lambda v: v == 10)

    # repair must still succeed via the fallback propose() path
    assert result.succeeded
    assert p.propose_calls == 1

    # exactly one stream_error event must have been emitted
    stream_errors = [e for e in events if e.type == "stream_error"]
    assert len(stream_errors) == 1
    assert stream_errors[0].error == error_message


def test_arun_emits_stream_error_with_error_payload():
    """async path: apropose_stream raising must emit stream_error with the
    exception message as the error field, then fall back to propose()."""
    source = "def f(x):\n    return x * 2\n"
    error_message = "async stream broken"

    class BrokenAsyncStream:
        def __init__(self):
            self.propose_calls = 0

        def propose(self, s, u):
            self.propose_calls += 1
            return source

        async def apropose_stream(self, s, u):
            raise RuntimeError(error_message)
            # async generator marker so Python treats this as an async generator
            # even though the raise is unconditional
            yield  # pragma: no cover

    p = BrokenAsyncStream()
    events: list[RepairEvent] = []
    loop = RepairLoop(
        max_attempts=2, proposer=p, on_event=lambda e: events.append(e)
    )

    def f(x):
        return None

    result = asyncio.run(loop.arun(f, args=(5,), verify=lambda v: v == 10))

    # repair must still succeed via the fallback propose() path
    assert result.succeeded
    assert p.propose_calls == 1

    # exactly one stream_error event must have been emitted
    stream_errors = [e for e in events if e.type == "stream_error"]
    assert len(stream_errors) == 1
    assert stream_errors[0].error == error_message


# ---------------------------------------------------------------------------
# Verify imports still work
# ---------------------------------------------------------------------------


def test_imports_do_not_require_sdk_clients():
    import importlib

    # These modules lazy-import their SDKs; importing self_heal.llm alone
    # should not blow up even without SDKs installed (they're present in
    # the dev env so this just asserts the structure).
    importlib.import_module("self_heal.llm")
    importlib.import_module("self_heal.events")
