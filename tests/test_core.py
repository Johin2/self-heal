"""Smoke tests for the repair loop + decorator.

Uses a scripted proposer so no real API calls are made.
"""

from __future__ import annotations

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


def test_first_call_succeeds_without_repair():
    proposer = ScriptedProposer([])

    @repair(max_attempts=3, proposer=proposer)
    def add(a, b):
        return a + b

    assert add(2, 3) == 5
    assert proposer.calls == []
    assert add.last_repair.succeeded
    assert add.last_repair.total_attempts == 1
    assert add.last_repair.attempts == []


def test_repair_loop_fixes_zero_division():
    repaired_src = (
        "def divide(a, b):\n"
        "    if b == 0:\n"
        "        return 0\n"
        "    return a / b\n"
    )
    proposer = ScriptedProposer([repaired_src])
    loop = RepairLoop(max_attempts=3, proposer=proposer)

    def divide(a, b):
        return a / b

    result = loop.run(divide, args=(10, 0))

    assert result.succeeded is True
    assert result.final_value == 0
    assert result.total_attempts == 2
    assert len(result.attempts) == 1
    assert result.attempts[0].failure.error_type == "ZeroDivisionError"
    assert result.attempts[0].succeeded is True
    assert len(proposer.calls) == 1


def test_repair_loop_extracts_code_from_markdown():
    markdown_response = (
        "Here's the fix:\n"
        "```python\n"
        "def divide(a, b):\n"
        "    return a / b if b else 0\n"
        "```\n"
        "Hope that helps."
    )
    proposer = ScriptedProposer([markdown_response])
    loop = RepairLoop(max_attempts=3, proposer=proposer)

    def divide(a, b):
        return a / b

    result = loop.run(divide, args=(10, 0))

    assert result.succeeded is True
    assert result.final_value == 0


def test_exhausts_attempts_and_fails_gracefully():
    bad_repair = (
        "def broken(x):\n"
        "    raise ValueError('still broken')\n"
    )
    proposer = ScriptedProposer([bad_repair, bad_repair])
    loop = RepairLoop(max_attempts=3, proposer=proposer)

    def broken(x):
        raise RuntimeError("initial failure")

    result = loop.run(broken, args=(1,))

    assert result.succeeded is False
    assert result.final_value is None
    assert len(result.attempts) == 3
    for attempt in result.attempts:
        assert attempt.succeeded is False


def test_handles_invalid_proposed_code():
    invalid_code = "this is not python code ::::"
    proposer = ScriptedProposer([invalid_code])
    loop = RepairLoop(max_attempts=2, proposer=proposer)

    def broken():
        raise ValueError("boom")

    result = loop.run(broken)

    assert result.succeeded is False
    assert result.attempts[0].error_after_repair is not None


def test_decorator_raises_after_exhausted_attempts():
    bad_repair = (
        "def always_fails(x):\n"
        "    raise ValueError('nope')\n"
    )
    proposer = ScriptedProposer([bad_repair])

    @repair(max_attempts=2, proposer=proposer, on_failure="raise")
    def always_fails(x):
        raise ValueError("initial")

    with pytest.raises(RuntimeError) as excinfo:
        always_fails(1)

    assert "self-heal exhausted" in str(excinfo.value)
    assert always_fails.last_repair is not None
    assert always_fails.last_repair.succeeded is False


def test_decorator_returns_none_on_failure_when_configured():
    bad_repair = (
        "def always_fails(x):\n"
        "    raise ValueError('nope')\n"
    )
    proposer = ScriptedProposer([bad_repair])

    @repair(max_attempts=2, proposer=proposer, on_failure="return_none")
    def always_fails(x):
        raise ValueError("initial")

    assert always_fails(1) is None


def test_rejects_invalid_max_attempts():
    with pytest.raises(ValueError):
        RepairLoop(max_attempts=0)
