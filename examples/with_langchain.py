"""Make any LangChain tool self-healing.

LangChain's `@tool` decorator wraps a function as a Tool. Stack `@repair`
inside so the underlying callable heals itself under load.

Install:
    pip install 'self-heal-llm[claude]' langchain-core

Requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

# from langchain_core.tools import tool  # langchain-core
from self_heal import repair


def test_roundtrips_positive(fn):
    assert fn(5) == 25


# @tool
@repair(
    max_attempts=3,
    verify=lambda r: isinstance(r, int) and r >= 0,
    tests=[test_roundtrips_positive],
)
def square(n: int) -> int:
    """Square a number. Self-healing."""
    return n + n  # naive: addition instead of multiplication


# The LangChain agent calls the Tool; self-heal silently heals the
# underlying function until it passes both the verifier and the test.
