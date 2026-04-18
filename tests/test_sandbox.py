"""Tests for the subprocess sandbox."""

from __future__ import annotations

import pytest

from self_heal import RepairLoop, SafetyConfig
from self_heal.sandbox import (
    SandboxError,
    SubprocessSandbox,
    make_sandboxed_callable,
)


class ScriptedProposer:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def propose(self, system, user):
        self.calls.append((system, user))
        return self._responses.pop(0)


def test_sandbox_runs_simple_function():
    sb = SubprocessSandbox(timeout=10.0)
    src = "def add(a, b):\n    return a + b\n"
    assert sb.run(src, "add", (2, 3), {}) == 5


def test_sandbox_preserves_exception_type():
    sb = SubprocessSandbox(timeout=10.0)
    src = "def boom():\n    raise ValueError('nope')\n"
    with pytest.raises(ValueError, match="nope"):
        sb.run(src, "boom", (), {})


def test_sandbox_rejects_missing_symbol():
    sb = SubprocessSandbox(timeout=10.0)
    src = "def other():\n    return 1\n"
    with pytest.raises(SandboxError, match="not callable"):
        sb.run(src, "missing", (), {})


def test_sandbox_timeout():
    sb = SubprocessSandbox(timeout=1.0)
    src = "def slow():\n    import time\n    time.sleep(5)\n    return 1\n"
    with pytest.raises(SandboxError, match="timed out"):
        sb.run(src, "slow", (), {})


def test_sandbox_rejects_unpickleable_args():
    sb = SubprocessSandbox(timeout=5.0)
    src = "def f(x):\n    return x\n"
    with pytest.raises(SandboxError, match="not pickleable"):
        sb.run(src, "f", (lambda y: y,), {})


def test_make_sandboxed_callable_behaves_like_fn():
    sb = SubprocessSandbox(timeout=10.0)
    src = "def mul(a, b):\n    return a * b\n"
    fn = make_sandboxed_callable(src, "mul", sb)
    assert fn.__name__ == "mul"
    assert fn(4, 5) == 20


def test_sandbox_isolates_from_caller_globals():
    """The sandbox must NOT see the caller's imports. Proposals that
    rely on implicit globals should fail in-sandbox, forcing them to
    be self-contained."""
    sb = SubprocessSandbox(timeout=10.0)
    # No import of math — running this in-process with our globals
    # might succeed, but under -I with a fresh namespace it must fail.
    src = "def f():\n    return math.pi\n"
    with pytest.raises(NameError):
        sb.run(src, "f", (), {})


def test_repair_loop_uses_sandbox_when_configured():
    good = "def divide(a, b):\n    return 0 if b == 0 else a / b\n"
    proposer = ScriptedProposer([good])
    safety = SafetyConfig(level="off", sandbox="subprocess", sandbox_timeout=10.0)
    loop = RepairLoop(max_attempts=3, proposer=proposer, safety=safety)

    def divide(a, b):
        return a / b

    result = loop.run(divide, args=(10, 0))
    assert result.succeeded
    assert result.final_value == 0
    # The winning callable is a sandbox wrapper.
    assert hasattr(result.attempts[-1], "proposed_source")


def test_repair_loop_without_sandbox_stays_in_process():
    """Sanity: default behavior unchanged."""
    good = "def divide(a, b):\n    return 0 if b == 0 else a / b\n"
    proposer = ScriptedProposer([good])
    loop = RepairLoop(max_attempts=3, proposer=proposer)

    def divide(a, b):
        return a / b

    result = loop.run(divide, args=(10, 0))
    assert result.succeeded
