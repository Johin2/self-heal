"""Decorator API for self-heal."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, Literal, TypeVar

from self_heal.llm import LLMProposer
from self_heal.loop import RepairLoop

F = TypeVar("F", bound=Callable[..., Any])


def repair(
    max_attempts: int = 3,
    model: str = "claude-sonnet-4-6",
    proposer: LLMProposer | None = None,
    verbose: bool = False,
    on_failure: Literal["raise", "return_none"] = "raise",
) -> Callable[[F], F]:
    """Wrap a function in an LLM-backed repair loop.

    Example:
        @repair(max_attempts=3)
        def my_function(x):
            return 1 / x

        my_function(0)            # self-heal catches, proposes fix, retries
        my_function.last_repair   # RepairResult with full attempt history

    Args:
        max_attempts: Max total calls (including the first one).
        model: Claude model ID used by the default proposer.
        proposer: Custom LLMProposer. Overrides `model` when provided.
        verbose: Log each attempt via the `self_heal` logger.
        on_failure: What to do when all attempts fail.
            - "raise": re-raise as RuntimeError with failure context.
            - "return_none": return None.

    Returns:
        The wrapped function. The wrapper exposes `last_repair` (RepairResult)
        and `repair_loop` (RepairLoop instance) as attributes.
    """

    def decorator(func: F) -> F:
        loop = RepairLoop(
            model=model,
            max_attempts=max_attempts,
            proposer=proposer,
            verbose=verbose,
        )

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = loop.run(func, args=args, kwargs=kwargs)
            wrapper.last_repair = result  # type: ignore[attr-defined]

            if result.succeeded:
                return result.final_value
            if on_failure == "return_none":
                return None

            if result.attempts:
                last = result.attempts[-1].failure
                raise RuntimeError(
                    f"self-heal exhausted {result.total_attempts} attempts for "
                    f"'{func.__name__}'. Last failure: "
                    f"{last.error_type}: {last.message}"
                )
            raise RuntimeError(
                f"self-heal: '{func.__name__}' failed with no recorded attempts"
            )

        wrapper.last_repair = None  # type: ignore[attr-defined]
        wrapper.repair_loop = loop  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator
