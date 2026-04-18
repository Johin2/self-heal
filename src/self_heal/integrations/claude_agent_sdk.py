"""First-class Claude Agent SDK integration.

The Claude Agent SDK exposes tools via `@tool(name, description, schema)`
on an async function. This module gives you a single decorator,
`healing_tool`, that combines that registration with self-heal's
`@repair` so the tool body heals itself on failure while the agent sees
a standard SDK tool.

Install:
    pip install 'self-heal-llm[claude]' claude-agent-sdk

Example:
    from self_heal.integrations.claude_agent_sdk import healing_tool

    def test_dollar_comma(fn):
        # The tool signature is `async (args: dict) -> dict`.
        # Test helpers still receive the raw callable.
        import asyncio
        result = asyncio.run(fn({"text": "$1,299"}))
        assert "1299" in result["content"][0]["text"]

    @healing_tool(
        "price_from_text",
        "Extract a numeric price from messy text.",
        {"text": str},
        verify=lambda r: isinstance(r, dict) and not r.get("is_error"),
        tests=[test_dollar_comma],
    )
    async def price_from_text(args):
        text = args["text"]
        return {
            "content": [{"type": "text", "text": str(float(text.replace("$", "")))}]
        }
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from self_heal.cache import RepairCache
from self_heal.core import repair as _repair
from self_heal.events import EventCallback
from self_heal.llm import LLMProposer
from self_heal.safety import SafetyConfig, SafetyLevel
from self_heal.verify import Test, Verifier

__all__ = ["healing_tool"]


def healing_tool(
    name: str,
    description: str,
    input_schema: type | dict[str, Any],
    annotations: Any = None,
    *,
    # ---- self-heal repair config ----
    max_attempts: int = 3,
    model: str = "claude-sonnet-4-6",
    proposer: LLMProposer | None = None,
    verbose: bool = False,
    on_failure: Literal["raise", "return_none"] = "raise",
    verify: Verifier | None = None,
    tests: list[Test] | None = None,
    prompt_extra: str | None = None,
    cache: RepairCache | None = None,
    cache_path: str | Path | None = None,
    safety: SafetyConfig | SafetyLevel | None = None,
    on_event: EventCallback | None = None,
):
    """Register an async function as a Claude Agent SDK tool with
    self-heal's repair loop underneath.

    The first four arguments are the Claude Agent SDK's `@tool`
    parameters. The rest are self-heal's `@repair` parameters. The
    wrapped function must be `async def`.

    Returns an `SdkMcpTool` ready for `create_sdk_mcp_server(...)`.
    """
    try:
        from claude_agent_sdk import tool as _sdk_tool
    except ImportError as err:  # pragma: no cover
        raise ImportError(
            "claude-agent-sdk is required for healing_tool. "
            "Install with: pip install claude-agent-sdk"
        ) from err

    def decorator(fn: Callable[[dict], Any]):
        healed = _repair(
            max_attempts=max_attempts,
            model=model,
            proposer=proposer,
            verbose=verbose,
            on_failure=on_failure,
            verify=verify,
            tests=tests,
            prompt_extra=prompt_extra,
            cache=cache,
            cache_path=cache_path,
            safety=safety,
            on_event=on_event,
        )(fn)

        # Claude Agent SDK accepts positional annotations at position 4.
        if annotations is None:
            return _sdk_tool(name, description, input_schema)(healed)
        return _sdk_tool(name, description, input_schema, annotations)(healed)

    return decorator
