"""Make any Claude Agent SDK tool self-healing.

Wrap your tool function with `@repair` BEFORE (or after — order doesn't
matter for the outer wrapping) the agent's tool decorator. Failures in
the tool body, including verifier/test failures, trigger an automatic
repair loop transparent to the agent.

Install:
    pip install 'self-heal-llm[claude]' claude-agent-sdk

Requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

# This example shows the INTEGRATION PATTERN — adapt imports and tool-
# registration syntax to the exact Claude Agent SDK version you're using.
#
# from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeSDKClient
from self_heal import repair


def test_handles_dollar_comma(fn):
    assert fn({"text": "$1,299"}) == 1299.0


def test_handles_rupee(fn):
    assert fn({"text": "₹500"}) == 500.0


# @tool("price_from_text", "Extract a price from messy text", {"text": str})
@repair(
    max_attempts=3,
    verify=lambda r: isinstance(r, float) and r > 0,
    tests=[test_handles_dollar_comma, test_handles_rupee],
)
async def price_from_text(args: dict) -> float:
    """A tool the agent can call. Self-healing under the hood."""
    text = args["text"]
    return float(text.replace("$", ""))  # naive


# When the agent invokes this tool with arbitrary user input,
# self-heal will repair the parser until it passes both tests
# AND the verifier — no manual error handling needed.
