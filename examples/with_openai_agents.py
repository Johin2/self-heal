"""Make any OpenAI Agents SDK tool self-healing.

The pattern mirrors the Claude Agent SDK example: wrap the raw function
with `@repair`, then register it with the agent framework's tool
decorator. All self-heal features — multi-turn memory, verifiers,
test-driven repair, async — work identically.

Install:
    pip install 'self-heal-llm[openai]' openai-agents

Requires OPENAI_API_KEY.
"""

from __future__ import annotations

# from agents import function_tool, Agent, Runner  # openai-agents SDK
from self_heal import repair
from self_heal.llm import OpenAIProposer


def test_returns_dict_with_city(fn):
    result = fn({"city": "Mumbai"})
    assert isinstance(result, dict)
    assert "city" in result


# @function_tool
@repair(
    max_attempts=3,
    proposer=OpenAIProposer(model="gpt-5"),
    tests=[test_returns_dict_with_city],
)
async def get_weather_for(args: dict) -> dict:
    """Fake weather tool. Agents call this; self-heal keeps it working."""
    city = args["city"]
    # Naive: forgets to wrap in dict, returns plain string.
    return f"Sunny in {city}"  # <- will fail the test


# The agent will not see the failures. It sees a working tool that
# returns well-structured results.
