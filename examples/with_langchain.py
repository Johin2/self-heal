"""Make any LangChain / LangGraph tool self-healing (first-class integration).

Use the `healing_tool` decorator to register a function as both a
LangChain `BaseTool` and a self-healing callable in one step. Works
inside LangChain chains, LangGraph agents, or anywhere a LangChain
tool is expected.

Install:
    pip install 'self-heal-llm[claude]' langchain-core langgraph

Requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

from self_heal.integrations.langgraph import healing_tool


def test_dollar_comma(fn):
    assert fn.invoke({"text": "$1,299"}) == 1299.0


def test_rupee(fn):
    assert fn.invoke({"text": "Rs 500"}) == 500.0


@healing_tool(
    "price_from_text",
    description="Extract a numeric price from messy text (handles $, commas, rupees).",
    max_attempts=3,
    verify=lambda r: isinstance(r, float) and r > 0,
    tests=[test_dollar_comma, test_rupee],
)
def price_from_text(text: str) -> float:
    """Naive: only handles '$X.YY'. Self-heal will repair on first
    call against a test or verifier failure."""
    return float(text.replace("$", ""))


# `price_from_text` is now a LangChain BaseTool. Bind it to an LLM or
# use it in a LangGraph agent the usual way:
#
#     from langgraph.prebuilt import create_react_agent
#     from langchain_anthropic import ChatAnthropic
#
#     agent = create_react_agent(
#         ChatAnthropic(model="claude-sonnet-4-6"),
#         tools=[price_from_text],
#     )
#
# The agent sees a standard LangChain tool; self-heal repairs the
# function until both tests and the verifier pass.
