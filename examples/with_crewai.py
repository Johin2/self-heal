"""Make any CrewAI tool self-healing.

CrewAI's `@tool` decorator wraps a Python function as an agent tool.
Stack `@repair` on the underlying callable so verifier and tests enforce
correct behavior while the agent keeps calling the same tool name.

Install:
    pip install 'self-heal-llm[gemini]' crewai

Requires GEMINI_API_KEY.
"""

from __future__ import annotations

# from crewai.tools import tool  # crewai
from self_heal import repair
from self_heal.llm import GeminiProposer


def test_handles_dollar_comma(fn):
    assert fn("$1,299") == 1299.0


def test_handles_rupee(fn):
    assert fn("Rs 500") == 500.0


# @tool("price_from_text")
@repair(
    max_attempts=3,
    proposer=GeminiProposer(model="gemini-2.5-pro"),
    verify=lambda r: isinstance(r, float) and r > 0,
    tests=[test_handles_dollar_comma, test_handles_rupee],
)
def price_from_text(text: str) -> float:
    """Extract numeric price from free-form text. Self-healing."""
    return float(text.replace("$", ""))  # naive: fails on commas/other symbols
