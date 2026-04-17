"""Tests for v0.2 features: cache, safety rails, callbacks, pytest plugin."""

from __future__ import annotations

import pytest

from self_heal import (
    RepairCache,
    RepairEvent,
    RepairLoop,
    SafetyConfig,
    UnsafeProposalError,
    repair,
)
from self_heal.safety import validate
from self_heal.types import Failure


class ScriptedProposer:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def propose(self, system, user):
        self.calls.append((system, user))
        if not self._responses:
            raise RuntimeError("ran out")
        return self._responses.pop(0)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def test_cache_records_and_replays_successful_repair(tmp_path):
    cache = RepairCache(tmp_path / "cache.db")

    good = "def divide(a, b):\n    return 0 if b == 0 else a / b\n"
    proposer = ScriptedProposer([good])
    loop = RepairLoop(max_attempts=3, proposer=proposer, cache=cache)

    def divide(a, b):
        return a / b

    # First call hits the LLM and populates the cache.
    r1 = loop.run(divide, args=(10, 0))
    assert r1.succeeded
    assert len(proposer.calls) == 1

    # Second call with a FRESH loop + same cache should skip the LLM.
    proposer2 = ScriptedProposer([])
    loop2 = RepairLoop(max_attempts=3, proposer=proposer2, cache=cache)
    r2 = loop2.run(divide, args=(10, 0))
    assert r2.succeeded
    assert proposer2.calls == []  # cached

    stats = cache.stats()
    assert stats["entries"] >= 1
    assert stats["total_hits"] >= 1

    cache.close()


def test_cache_miss_for_different_failure(tmp_path):
    cache = RepairCache(tmp_path / "cache.db")
    fake_a = Failure(kind="exception", error_type="ValueError", message="boom A")
    fake_b = Failure(kind="exception", error_type="ValueError", message="boom B")

    cache.record("def f(): pass", fake_a, "def f(): return 1", True)
    assert cache.lookup("def f(): pass", fake_a) == "def f(): return 1"
    assert cache.lookup("def f(): pass", fake_b) is None

    cache.close()


# ---------------------------------------------------------------------------
# Safety rails
# ---------------------------------------------------------------------------


def test_safety_blocks_eval():
    with pytest.raises(UnsafeProposalError):
        validate(
            "def f(x):\n    return eval(x)\n",
            SafetyConfig(level="moderate"),
        )


def test_safety_blocks_subprocess_import():
    with pytest.raises(UnsafeProposalError):
        validate(
            "import subprocess\ndef f():\n    subprocess.run(['ls'])\n",
            SafetyConfig(level="moderate"),
        )


def test_safety_blocks_os_system():
    with pytest.raises(UnsafeProposalError):
        validate(
            "import os\ndef f():\n    os.system('rm -rf /')\n",
            SafetyConfig(level="moderate"),
        )


def test_safety_allows_safe_code():
    validate(
        "import re\ndef f(s):\n    return re.sub(r'\\s+', ' ', s)\n",
        SafetyConfig(level="moderate"),
    )


def test_safety_strict_blocks_non_whitelisted_imports():
    with pytest.raises(UnsafeProposalError):
        validate(
            "import urllib.request\ndef f():\n    pass\n",
            SafetyConfig(level="strict"),
        )


def test_safety_strict_allows_whitelisted_stdlib():
    validate(
        "import math\ndef f(x):\n    return math.sqrt(x)\n",
        SafetyConfig(level="strict"),
    )


def test_safety_off_allows_everything():
    validate(
        "import subprocess\ndef f():\n    subprocess.run(['ls'])\n",
        SafetyConfig(level="off"),
    )


def test_loop_rejects_unsafe_proposal_and_records_error():
    unsafe = "import subprocess\ndef broken():\n    subprocess.run(['ls'])\n"
    fallback = "def broken():\n    return 0\n"
    proposer = ScriptedProposer([unsafe, fallback])
    loop = RepairLoop(
        max_attempts=3,
        proposer=proposer,
        safety=SafetyConfig(level="moderate"),
    )

    def broken():
        raise ValueError("boom")

    result = loop.run(broken)

    assert result.succeeded is True
    assert result.final_value == 0
    assert "safety:" in (result.attempts[0].error_after_repair or "")


# ---------------------------------------------------------------------------
# Event callbacks
# ---------------------------------------------------------------------------


def test_on_event_fires_for_complete_repair():
    repaired = "def divide(a, b):\n    return 0 if b == 0 else a / b\n"
    proposer = ScriptedProposer([repaired])
    events: list[RepairEvent] = []

    loop = RepairLoop(
        max_attempts=3,
        proposer=proposer,
        on_event=events.append,
    )

    def divide(a, b):
        return a / b

    loop.run(divide, args=(10, 0))

    types = [e.type for e in events]
    assert "attempt_start" in types
    assert "attempt_failed" in types
    assert "propose_start" in types
    assert "propose_complete" in types
    assert "install_success" in types
    assert "verify_success" in types
    assert "repair_succeeded" in types


def test_on_event_fires_cache_miss(tmp_path):
    cache = RepairCache(tmp_path / "cache.db")

    events: list[RepairEvent] = []
    proposer = ScriptedProposer(
        ["def divide(a, b):\n    return 0 if b == 0 else a / b\n"]
    )
    loop = RepairLoop(
        max_attempts=3,
        proposer=proposer,
        cache=cache,
        on_event=events.append,
    )

    def divide(a, b):
        return a / b

    loop.run(divide, args=(10, 0))
    types = [e.type for e in events]
    assert "cache_miss" in types

    cache.close()


def test_on_event_is_robust_to_observer_errors():
    """A buggy callback must not crash the repair loop."""
    repaired = "def f(x):\n    return 1\n"
    proposer = ScriptedProposer([repaired])

    def bad_callback(event):
        raise RuntimeError("observer buggy")

    loop = RepairLoop(max_attempts=3, proposer=proposer, on_event=bad_callback)

    def f(x):
        raise ValueError("boom")

    result = loop.run(f, args=(1,))
    assert result.succeeded is True


# ---------------------------------------------------------------------------
# Decorator-level integration
# ---------------------------------------------------------------------------


def test_repair_decorator_accepts_safety_string():
    repaired = "def f(x):\n    return 1\n"
    proposer = ScriptedProposer([repaired])

    @repair(max_attempts=3, proposer=proposer, safety="moderate")
    def f(x):
        raise ValueError("boom")

    assert f(1) == 1


def test_repair_decorator_accepts_cache_path(tmp_path):
    repaired = "def f(x):\n    return 1\n"
    proposer = ScriptedProposer([repaired])

    @repair(
        max_attempts=3,
        proposer=proposer,
        cache_path=tmp_path / "c.db",
    )
    def f(x):
        raise ValueError("boom")

    assert f(1) == 1
    assert f.repair_loop.cache is not None
    f.repair_loop.cache.close()
