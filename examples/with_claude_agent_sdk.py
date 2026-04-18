"""Make any Claude Agent SDK tool self-healing (first-class integration).

Use the `healing_tool` decorator to register an async function as both a
Claude Agent SDK tool and a self-healing callable in one step.

Install:
    pip install 'self-heal-llm[claude]' claude-agent-sdk

Requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import asyncio

from self_heal.integrations.claude_agent_sdk import healing_tool


def test_dollar_comma(fn):
    result = asyncio.run(fn({"text": "$1,299"}))
    text = result["content"][0]["text"]
    assert "1299" in text


def test_rupee(fn):
    result = asyncio.run(fn({"text": "Rs 500"}))
    text = result["content"][0]["text"]
    assert "500" in text


@healing_tool(
    "price_from_text",
    "Extract a numeric price from messy text (handles $, commas, rupees).",
    {"text": str},
    max_attempts=3,
    verify=lambda r: isinstance(r, dict) and not r.get("is_error"),
    tests=[test_dollar_comma, test_rupee],
)
async def price_from_text(args):
    """Naive: only handles '$X.YY'. Self-heal will repair on first call
    against a test or verifier failure."""
    text = args["text"]
    return {
        "content": [{"type": "text", "text": str(float(text.replace("$", "")))}]
    }


# `price_from_text` is now an SdkMcpTool. Register it with an SDK MCP
# server the usual way:
#
#     from claude_agent_sdk import create_sdk_mcp_server, ClaudeSDKClient
#     server = create_sdk_mcp_server("demo", tools=[price_from_text])
#     client = ClaudeSDKClient(mcp_servers={"demo": server})
#
# The agent sees a standard tool; under the hood, self-heal repairs the
# function until both tests and the verifier pass.
