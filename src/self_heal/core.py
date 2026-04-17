"""Decorator API for self-heal."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, Literal, TypeVar

from self_heal.cache import RepairCache
from self_heal.events import EventCallback
from self_heal.llm import LLMProposer
from self_heal.loop import RepairLoop
from self_heal.safety import SafetyConfig, SafetyLevel
from self_heal.verify import Test, Verifier

F = TypeVar("F", bound=Callable[..., Any])


def repair(
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
) -> Callable[[F], F]:
    """Wrap a function in an LLM-backed repair loop.

    Works with both sync and async functions; the decorator auto-detects.

    Args:
        max_attempts: Max total calls (including the first one).
        model: Claude model ID used by the default proposer.
        proposer: Custom LLMProposer. Overrides `model` when provided.
        verbose: Log each attempt via the `self_heal` logger.
        on_failure: "raise" (default) re-raises as RuntimeError with context,
            "return_none" returns None.
        verify: Optional predicate / raising check on the return value.
        tests: Optional list of callables; each takes the current function
            and raises on failure.
        prompt_extra: Free-form user text appended to every repair prompt.
        cache: Optional pre-built `RepairCache`. Takes priority over
            `cache_path`.
        cache_path: Shortcut that creates `RepairCache(cache_path)`.
        safety: "off" | "moderate" | "strict" | a `SafetyConfig`. Enables
            AST-based safety checks on every proposal before it is exec'd.
        on_event: Callback invoked on each repair event (attempt start,
            failure, cache hit, etc.). See `self_heal.events.RepairEvent`.

    Returns:
        The wrapped function. Exposes:
            - `last_repair` (RepairResult) — set after each call
            - `repair_loop` (RepairLoop) — the underlying loop
    """

    resolved_cache = cache
    if resolved_cache is None and cache_path is not None:
        resolved_cache = RepairCache(cache_path)

    resolved_safety: SafetyConfig | None
    if safety is None:
        resolved_safety = None
    elif isinstance(safety, SafetyConfig):
        resolved_safety = safety
    else:
        resolved_safety = SafetyConfig(level=safety)

    def decorator(func: F) -> F:
        loop = RepairLoop(
            model=model,
            max_attempts=max_attempts,
            proposer=proposer,
            verbose=verbose,
            cache=resolved_cache,
            safety=resolved_safety,
            on_event=on_event,
        )

        is_async = inspect.iscoroutinefunction(func)

        if is_async:

            @wraps(func)
            async def awrapper(*args: Any, **kwargs: Any) -> Any:
                result = await loop.arun(
                    func,
                    args=args,
                    kwargs=kwargs,
                    verify=verify,
                    tests=tests,
                    prompt_extra=prompt_extra,
                )
                awrapper.last_repair = result  # type: ignore[attr-defined]
                return _finalize(result, func, on_failure)

            awrapper.last_repair = None  # type: ignore[attr-defined]
            awrapper.repair_loop = loop  # type: ignore[attr-defined]
            return awrapper  # type: ignore[return-value]

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = loop.run(
                func,
                args=args,
                kwargs=kwargs,
                verify=verify,
                tests=tests,
                prompt_extra=prompt_extra,
            )
            wrapper.last_repair = result  # type: ignore[attr-defined]
            return _finalize(result, func, on_failure)

        wrapper.last_repair = None  # type: ignore[attr-defined]
        wrapper.repair_loop = loop  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


def _finalize(result, func, on_failure: str) -> Any:
    if result.succeeded:
        return result.final_value
    if on_failure == "return_none":
        return None
    if result.attempts:
        last = result.attempts[-1].failure
        raise RuntimeError(
            f"self-heal exhausted {result.total_attempts} attempts for "
            f"'{func.__name__}'. Last failure: {last.error_type}: {last.message}"
        )
    raise RuntimeError(
        f"self-heal: '{func.__name__}' failed with no recorded attempts"
    )
