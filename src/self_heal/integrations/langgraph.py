"""First-class LangChain / LangGraph integration.

LangGraph tools are LangChain tools (langchain_core's `@tool` decorator).
This module gives you a single decorator, `healing_tool`, that combines
LangChain's tool registration with self-heal's `@repair` loop so the
underlying callable heals itself on failure while the graph sees a
standard LangChain `BaseTool`.

Install:
    pip install 'self-heal-llm[claude]' langchain-core langgraph

Example:
    from self_heal.integrations.langgraph import healing_tool

    def test_dollar_comma(fn):
        # LangChain tools take keyword args matching the function's
        # declared parameters. Test helpers still receive the callable.
        assert fn.invoke({"text": "$1,299"}) == 1299.0

    @healing_tool(
        "price_from_text",
        description="Extract a numeric price from messy text.",
        verify=lambda r: isinstance(r, float) and r > 0,
        tests=[test_dollar_comma],
    )
    def price_from_text(text: str) -> float:
        return float(text.replace("$", ""))  # naive

Use the returned BaseTool in a LangGraph agent, a LangChain chain, or
anywhere else a LangChain tool is expected.
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
    name_or_callable: str | Callable | None = None,
    *,
    # ---- passthrough to langchain_core's @tool ----
    description: str | None = None,
    args_schema: Any = None,
    return_direct: bool = False,
    infer_schema: bool = True,
    parse_docstring: bool = False,
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
    """Register a function as both a LangChain tool and a self-healing
    callable in one decorator.

    The first parameter and the first group of keyword arguments mirror
    `langchain_core.tools.tool`. The second group is `@repair`. The
    wrapped function can be sync or async; the decorator auto-detects.

    Returns a `BaseTool` ready for LangGraph / LangChain. The repair
    loop runs under `.invoke(...)` and `.ainvoke(...)` calls; an agent
    that invokes this tool gets the standard tool contract.
    """
    try:
        from langchain_core.tools import tool as _lc_tool
    except ImportError as err:  # pragma: no cover
        raise ImportError(
            "langchain-core is required for LangGraph integration. "
            "Install with: pip install langchain-core langgraph"
        ) from err

    def _apply_repair(fn: Callable) -> Callable:
        return _repair(
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

    # langchain_core's @tool accepts multiple calling conventions:
    #   @tool
    #   def fn(...): ...
    #   @tool("name")
    #   def fn(...): ...
    #   @tool("name", description=...)
    #   def fn(...): ...
    # We want to preserve all of them. If `name_or_callable` is a
    # callable, the user wrote `@healing_tool` without parentheses.
    if callable(name_or_callable):
        fn = name_or_callable
        healed = _apply_repair(fn)
        return _lc_tool(
            description=description,
            args_schema=args_schema,
            return_direct=return_direct,
            infer_schema=infer_schema,
            parse_docstring=parse_docstring,
        )(healed)

    def decorator(fn: Callable):
        healed = _apply_repair(fn)
        lc_kwargs: dict[str, Any] = {
            "description": description,
            "args_schema": args_schema,
            "return_direct": return_direct,
            "infer_schema": infer_schema,
            "parse_docstring": parse_docstring,
        }
        # langchain_core's @tool rejects args_schema=None + infer_schema=True
        # in some versions; prune None values to be safe.
        lc_kwargs = {k: v for k, v in lc_kwargs.items() if v is not None}
        if name_or_callable is None:
            return _lc_tool(**lc_kwargs)(healed)
        return _lc_tool(name_or_callable, **lc_kwargs)(healed)

    return decorator
