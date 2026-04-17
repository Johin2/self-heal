"""Tests for v0.1 features: verifiers, tests, multi-turn memory, async."""

from __future__ import annotations

import asyncio

import pytest

from self_heal import RepairLoop, repair


class ScriptedProposer:
    """Deterministic proposer: returns pre-scripted code for each call."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def propose(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if not self._responses:
            raise RuntimeError("ScriptedProposer ran out of responses")
        return self._responses.pop(0)


# ---------------------------------------------------------------------------
# Verifiers
# ---------------------------------------------------------------------------


def test_verifier_triggers_repair_when_predicate_returns_false():
    repaired = "def get_value(x):\n    return x * 2\n"
    proposer = ScriptedProposer([repaired])
    loop = RepairLoop(max_attempts=3, proposer=proposer)

    def get_value(x):
        return x  # returns 5, but verifier wants > 5

    result = loop.run(
        get_value,
        args=(5,),
        verify=lambda v: v > 5,
    )

    assert result.succeeded is True
    assert result.final_value == 10
    assert len(result.attempts) == 1
    assert result.attempts[0].failure.kind == "verifier"
    assert result.attempts[0].succeeded is True


def test_verifier_raising_is_captured_as_failure():
    repaired = "def get_value(x):\n    return float(x)\n"
    proposer = ScriptedProposer([repaired])
    loop = RepairLoop(max_attempts=3, proposer=proposer)

    def raising_verifier(value):
        if not isinstance(value, float):
            raise TypeError(f"expected float, got {type(value).__name__}")
        return True

    def get_value(x):
        return x  # int, not float

    result = loop.run(get_value, args=(5,), verify=raising_verifier)

    assert result.succeeded is True
    assert result.final_value == 5.0
    assert result.attempts[0].failure.kind == "verifier"
    assert result.attempts[0].failure.error_type == "TypeError"


def test_verifier_success_skips_repair():
    proposer = ScriptedProposer([])
    loop = RepairLoop(max_attempts=3, proposer=proposer)

    def identity(x):
        return x

    result = loop.run(identity, args=(42,), verify=lambda v: v == 42)

    assert result.succeeded is True
    assert result.final_value == 42
    assert proposer.calls == []
    assert result.attempts == []


# ---------------------------------------------------------------------------
# Test-driven repair
# ---------------------------------------------------------------------------


def test_tests_trigger_repair_when_any_test_fails():
    repaired = (
        "def double(x):\n"
        "    return x * 2\n"
    )
    proposer = ScriptedProposer([repaired])
    loop = RepairLoop(max_attempts=3, proposer=proposer)

    def double(x):
        return x + 1  # wrong, should multiply

    def test_doubles_positive(fn):
        assert fn(3) == 6

    def test_doubles_negative(fn):
        assert fn(-2) == -4

    result = loop.run(
        double,
        args=(3,),
        tests=[test_doubles_positive, test_doubles_negative],
    )

    assert result.succeeded is True
    assert result.final_value == 6
    assert result.attempts[0].failure.kind == "test"
    assert "test_doubles_positive" in result.attempts[0].failure.message


def test_tests_success_passes_through():
    proposer = ScriptedProposer([])
    loop = RepairLoop(max_attempts=3, proposer=proposer)

    def add_one(x):
        return x + 1

    def test_increments(fn):
        assert fn(5) == 6

    result = loop.run(add_one, args=(5,), tests=[test_increments])

    assert result.succeeded is True
    assert result.final_value == 6
    assert proposer.calls == []


def test_tests_must_all_pass():
    repaired = "def f(x):\n    return x + 10\n"
    proposer = ScriptedProposer([repaired])
    loop = RepairLoop(max_attempts=3, proposer=proposer)

    def f(x):
        return x + 5  # passes test_a but fails test_b

    def test_a(fn):
        assert fn(0) > 0

    def test_b(fn):
        assert fn(0) == 10

    result = loop.run(f, args=(0,), tests=[test_a, test_b])

    assert result.succeeded is True
    assert result.final_value == 10
    assert result.attempts[0].failure.kind == "test"


# ---------------------------------------------------------------------------
# Multi-turn memory — prior failed attempts go into the next prompt
# ---------------------------------------------------------------------------


def test_prior_failed_attempts_are_included_in_next_prompt():
    first_bad = "def divide(a, b):\n    raise ValueError('nope1')\n"
    second_bad = "def divide(a, b):\n    raise ValueError('nope2')\n"
    final_good = "def divide(a, b):\n    return 0 if b == 0 else a / b\n"
    proposer = ScriptedProposer([first_bad, second_bad, final_good])
    loop = RepairLoop(max_attempts=4, proposer=proposer)

    def divide(a, b):
        return a / b

    result = loop.run(divide, args=(10, 0))

    assert result.succeeded is True
    assert result.final_value == 0
    assert len(proposer.calls) == 3

    # The third (final) prompt must reference both prior failed attempts.
    _, third_user = proposer.calls[2]
    assert "PREVIOUS REPAIR ATTEMPTS" in third_user
    assert "nope1" in third_user
    assert "nope2" in third_user
    assert "Attempt 1" in third_user
    assert "Attempt 2" in third_user


def test_first_prompt_has_no_history_section():
    bad = "def f(x):\n    raise ValueError('still bad')\n"
    proposer = ScriptedProposer([bad])
    loop = RepairLoop(max_attempts=2, proposer=proposer)

    def f(x):
        return 1 / 0

    loop.run(f, args=(1,))

    _, first_user = proposer.calls[0]
    assert "PREVIOUS REPAIR ATTEMPTS" not in first_user


# ---------------------------------------------------------------------------
# prompt_extra is threaded through
# ---------------------------------------------------------------------------


def test_prompt_extra_is_appended_to_user_prompt():
    repaired = "def f(x):\n    return 1\n"
    proposer = ScriptedProposer([repaired])
    loop = RepairLoop(max_attempts=2, proposer=proposer)

    def f(x):
        raise ValueError("boom")

    loop.run(f, args=(1,), prompt_extra="IMPORTANT: always return 1.")

    _, user_prompt = proposer.calls[0]
    assert "ADDITIONAL USER INSTRUCTIONS" in user_prompt
    assert "always return 1." in user_prompt


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


def test_repair_decorator_handles_async_function():
    repaired = "async def fetch(x):\n    return x + 1\n"
    proposer = ScriptedProposer([repaired])

    @repair(max_attempts=3, proposer=proposer)
    async def fetch(x):
        raise RuntimeError("network down")

    result = asyncio.run(fetch(5))

    assert result == 6
    assert fetch.last_repair.succeeded is True
    assert fetch.last_repair.attempts[0].failure.error_type == "RuntimeError"


def test_async_repair_with_verifier():
    repaired = "async def compute(x):\n    return x * 10\n"
    proposer = ScriptedProposer([repaired])

    @repair(max_attempts=3, proposer=proposer, verify=lambda v: v >= 40)
    async def compute(x):
        return x  # 5 — fails verifier

    result = asyncio.run(compute(5))

    assert result == 50
    assert compute.last_repair.attempts[0].failure.kind == "verifier"


def test_async_repair_exhausts_and_raises():
    bad = "async def always(x):\n    raise ValueError('still bad')\n"
    proposer = ScriptedProposer([bad])

    @repair(max_attempts=2, proposer=proposer)
    async def always(x):
        raise RuntimeError("initial")

    with pytest.raises(RuntimeError) as excinfo:
        asyncio.run(always(1))

    assert "self-heal exhausted" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Pending-attempt bookkeeping (no duplicate attempts on repair-install fail)
# ---------------------------------------------------------------------------


def test_invalid_proposed_code_marks_attempt_with_error_after_repair():
    invalid_code = "this is not python ::::"
    proposer = ScriptedProposer([invalid_code])
    loop = RepairLoop(max_attempts=2, proposer=proposer)

    def broken():
        raise ValueError("boom")

    result = loop.run(broken)

    assert result.succeeded is False
    assert result.attempts[0].error_after_repair is not None
    assert result.attempts[0].proposed_source is None
