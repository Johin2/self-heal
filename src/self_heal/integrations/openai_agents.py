"""First-class OpenAI Agents SDK integration.

The OpenAI Agents SDK exposes tools via `@function_tool` on a function.
This module gives you a single decorator, `healing_tool`, that combines
that registration with self-heal's `@repair` so the tool body heals
itself on failure while the agent sees a standard SDK tool.

Install:
    pip install 'self-heal-llm[openai]' openai-agents

Example:
    from self_heal.integrations.openai_agents import healing_tool

    def test_returns_dict(fn):
        import asyncio
        result = asyncio.run(fn({"city": "Mumbai"}))
        assert isinstance(result, dict) and "city" in result

    @healing_tool(
        verify=lambda r: isinstance(r, dict) and "city" in r,
        tests=[test_returns_dict],
    )
    async def get_weather(args: dict) -> dict:
        city = args["city"]
        return {"city": city, "forecast": "sunny"}
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
    # ---- openai-agents pass-through ----
    name_override: str | None = None,
    description_override: str | None = None,
) -> Callable:
    """Decorate a function as an OpenAI Agents SDK tool with self-heal repair.

    The decorated function is first wrapped by `@repair`, then registered
    with `@function_tool`. Any keyword arguments not consumed by self-heal
    are forwarded to `function_tool`.

    The wrapped function may be sync or async; self-heal handles both.
    """
    try:
        from agents import function_tool as _function_tool
    except ImportError as err:  # pragma: no cover
        raise ImportError(
            "openai-agents is required for healing_tool. "
            "Install with: pip install openai-agents"
        ) from err

    def decorator(fn: Callable[..., Any]) -> Any:
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

        ft_kwargs: dict[str, Any] = {}
        if name_override is not None:
            ft_kwargs["name_override"] = name_override
        if description_override is not None:
            ft_kwargs["description_override"] = description_override

        return _function_tool(**ft_kwargs)(healed) if ft_kwargs else _function_tool(healed)

    return decorator
