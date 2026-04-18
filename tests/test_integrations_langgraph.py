"""Tests for the LangChain / LangGraph integration.

No network calls. Uses ScriptedProposer for the repair loop.
"""

from __future__ import annotations

import pytest

pytest.importorskip("langchain_core")

from self_heal.integrations.langgraph import healing_tool  # noqa: E402


class ScriptedProposer:
    def __init__(self, responses):
        self._responses = list(responses)

    def propose(self, system, user):
        return self._responses.pop(0)


def test_healing_tool_returns_base_tool():
    from langchain_core.tools.base import BaseTool

    @healing_tool("noop", description="Smoke test.")
    def noop(x: int) -> int:
        return x

    assert isinstance(noop, BaseTool)
    assert noop.name == "noop"


def test_healing_tool_healed_body_runs():
    @healing_tool("echo", description="Echo a number.")
    def echo(n: int) -> int:
        return n

    assert echo.invoke({"n": 7}) == 7


def test_healing_tool_triggers_repair_on_verifier_failure():
    good_source = (
        "def parse_price(text: str) -> float:\n"
        '    return float(text.replace("$", "").replace(",", ""))\n'
    )
    proposer = ScriptedProposer([good_source])

    @healing_tool(
        "parse_price",
        description="Extract price.",
        max_attempts=3,
        proposer=proposer,
        verify=lambda r: isinstance(r, float) and r > 0,
    )
    def parse_price(text: str) -> float:
        return float(text.replace("$", ""))

    assert parse_price.invoke({"text": "$1,299"}) == 1299.0


def test_healing_tool_without_parens():
    """Bare @healing_tool decoration (no args) should also work."""

    @healing_tool
    def add(a: int, b: int) -> int:
        """Add two ints."""
        return a + b

    from langchain_core.tools.base import BaseTool

    assert isinstance(add, BaseTool)
    assert add.invoke({"a": 2, "b": 3}) == 5


def test_healing_tool_import_error_surface():
    """Source-level guard for a clear error when langchain-core is
    missing. We don't exercise the real ImportError path here because
    it requires uninstalling langchain-core mid-test, which is flaky."""
    import inspect

    from self_heal.integrations import langgraph as m

    src = inspect.getsource(m.healing_tool)
    assert "from langchain_core.tools import tool" in src
    assert "langchain-core is required" in src
