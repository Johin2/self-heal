"""Core repair loop (sync + async)."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable
from typing import Any

from self_heal.diagnose import classify
from self_heal.llm import LLMProposer
from self_heal.propose import build_messages, extract_code
from self_heal.types import RepairAttempt, RepairResult
from self_heal.verify import Test, Verifier, check_tests, check_verifier

logger = logging.getLogger("self_heal")


_INSTALL_HINT = (
    "No LLM proposer configured and the default (ClaudeProposer) could not load.\n"
    "Install an LLM SDK:\n"
    "  pip install 'self-heal-llm[claude]'     # Anthropic Claude (default)\n"
    "  pip install 'self-heal-llm[openai]'     # OpenAI + OpenAI-compatible endpoints\n"
    "  pip install 'self-heal-llm[gemini]'     # Google Gemini\n"
    "  pip install 'self-heal-llm[litellm]'    # 100+ providers via LiteLLM\n"
    "Or pass your own: RepairLoop(proposer=MyProposer())"
)


class RepairLoop:
    """Iteratively repair a failing callable using an LLM.

    The loop catches exceptions, runs optional verifier + tests, then
    proposes an LLM-backed repair that has access to the full history
    of prior failed attempts. Same loop powers both `@repair` and `@arepair`.

    Example:
        loop = RepairLoop(max_attempts=3)
        result = loop.run(my_function, args=(1, 2))
        if result.succeeded:
            print(result.final_value)
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        max_attempts: int = 3,
        proposer: LLMProposer | None = None,
        verbose: bool = False,
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.max_attempts = max_attempts
        self.verbose = verbose
        self._model = model
        self._proposer: LLMProposer | None = proposer

    @property
    def proposer(self) -> LLMProposer:
        """Return the configured proposer, creating the default lazily."""
        if self._proposer is None:
            try:
                from self_heal.llm import ClaudeProposer
            except ImportError as err:
                raise ImportError(_INSTALL_HINT) from err
            self._proposer = ClaudeProposer(model=self._model)
        return self._proposer

    # ------------------------------------------------------------------
    # Public runners
    # ------------------------------------------------------------------

    def run(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict | None = None,
        verify: Verifier | None = None,
        tests: list[Test] | None = None,
        prompt_extra: str | None = None,
    ) -> RepairResult:
        """Call `func(*args, **kwargs)` (sync), repairing until it succeeds.

        - `verify(result)` — predicate / raising check on the return value.
        - `tests` — each callable takes the current function and raises on failure.
        - `prompt_extra` — free-form user hint appended to every repair prompt.
        """
        ctx = _RunContext(
            loop=self,
            func=func,
            args=args,
            kwargs=kwargs or {},
            verify=verify,
            tests=tests,
            prompt_extra=prompt_extra,
        )

        for attempt_num in range(1, self.max_attempts + 1):
            result, finished = ctx.try_call(attempt_num)
            if finished:
                return result

            if attempt_num == self.max_attempts:
                return ctx.final_failure()

            raw = self._propose(ctx)
            ctx.apply_proposal(raw, attempt_num)

        return ctx.final_failure()

    async def arun(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict | None = None,
        verify: Verifier | None = None,
        tests: list[Test] | None = None,
        prompt_extra: str | None = None,
    ) -> RepairResult:
        """Async variant of `run`. Awaits coroutine functions and runs the
        (sync) proposer in a thread-pool executor so the event loop stays free.
        """
        ctx = _RunContext(
            loop=self,
            func=func,
            args=args,
            kwargs=kwargs or {},
            verify=verify,
            tests=tests,
            prompt_extra=prompt_extra,
        )

        for attempt_num in range(1, self.max_attempts + 1):
            result, finished = await ctx.atry_call(attempt_num)
            if finished:
                return result

            if attempt_num == self.max_attempts:
                return ctx.final_failure()

            raw = await asyncio.to_thread(self._propose, ctx)
            ctx.apply_proposal(raw, attempt_num)

        return ctx.final_failure()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _propose(self, ctx: _RunContext) -> str:
        self._log("Proposing repair...")
        system, user = build_messages(
            ctx.original_source,
            ctx.last_failure,
            history=list(ctx.attempts),
            extra=ctx.prompt_extra,
        )
        return self.proposer.propose(system, user)

    def _log(self, message: str) -> None:
        if self.verbose:
            logger.info("[self-heal] %s", message)

    @staticmethod
    def _recompile(source: str, name: str, original: Callable) -> Callable:
        namespace: dict[str, Any] = dict(original.__globals__)
        exec(source, namespace)  # noqa: S102
        if name not in namespace:
            raise RuntimeError(f"Proposed code did not define function '{name}'")
        new_func = namespace[name]
        if not callable(new_func):
            raise RuntimeError(f"'{name}' in proposed code is not callable")
        return new_func

    @staticmethod
    def _safe_source(func: Callable) -> str:
        try:
            return inspect.getsource(func)
        except (OSError, TypeError):
            return f"# Source unavailable for {func.__name__}\n"


class _RunContext:
    """Per-run state for RepairLoop (sync and async share this)."""

    def __init__(
        self,
        loop: RepairLoop,
        func: Callable,
        args: tuple,
        kwargs: dict,
        verify: Verifier | None,
        tests: list[Test] | None,
        prompt_extra: str | None,
    ):
        self.loop = loop
        self.original = func
        self.current = func
        self.args = args
        self.kwargs = kwargs
        self.verify = verify
        self.tests = tests
        self.prompt_extra = prompt_extra
        self.attempts: list[RepairAttempt] = []
        self.original_source = RepairLoop._safe_source(func)
        self.last_failure = None  # set on first failure

    # -- sync call path --------------------------------------------------

    def try_call(self, attempt_num: int) -> tuple[RepairResult, bool]:
        try:
            value = self.current(*self.args, **self.kwargs)
        except Exception as exc:
            self._record_failure(
                classify(exc, {"args": list(self.args), "kwargs": self.kwargs}),
                attempt_num,
            )
            return None, False
        return self._post_call(value, attempt_num)

    # -- async call path -------------------------------------------------

    async def atry_call(self, attempt_num: int) -> tuple[RepairResult, bool]:
        try:
            value = self.current(*self.args, **self.kwargs)
            if inspect.iscoroutine(value):
                value = await value
        except Exception as exc:
            self._record_failure(
                classify(exc, {"args": list(self.args), "kwargs": self.kwargs}),
                attempt_num,
            )
            return None, False
        return self._post_call(value, attempt_num)

    # -- shared -----------------------------------------------------------

    def _post_call(
        self, value: Any, attempt_num: int
    ) -> tuple[RepairResult, bool]:
        inputs_ctx = {"args": list(self.args), "kwargs": self.kwargs}

        vf = check_verifier(value, self.verify, inputs=inputs_ctx)
        if vf is not None:
            self._record_failure(vf, attempt_num)
            return None, False

        tf = check_tests(self.current, self.tests)
        if tf is not None:
            self._record_failure(tf, attempt_num)
            return None, False

        # Success — mark the last repair attempt (if any) as the one that worked.
        if self.attempts:
            self.attempts[-1].succeeded = True
            self.loop._log(f"Attempt {attempt_num} succeeded after repair.")

        return (
            RepairResult(
                succeeded=True,
                final_value=value,
                attempts=self.attempts,
                total_attempts=attempt_num,
            ),
            True,
        )

    def _record_failure(self, failure, attempt_num: int) -> None:
        self.last_failure = failure
        self.loop._log(
            f"Attempt {attempt_num} failed: {failure.error_type}: {failure.message}"
        )
        # Placeholder attempt; proposed_source filled later when we propose a fix.
        self.attempts.append(
            RepairAttempt(
                attempt_number=attempt_num,
                failure=failure,
                proposed_source=None,
                succeeded=False,
            )
        )

    def apply_proposal(self, raw: str, attempt_num: int) -> None:
        try:
            proposed = extract_code(raw)
            repaired = RepairLoop._recompile(
                proposed, self.original.__name__, self.original
            )
        except Exception as repair_exc:
            self.loop._log(f"Repair step itself failed: {repair_exc}")
            # Update the pending attempt with the repair-install error.
            self.attempts[-1].error_after_repair = str(repair_exc)
            return

        self.attempts[-1].proposed_source = proposed
        self.current = repaired
        self.loop._log("Repair applied, retrying...")

    def final_failure(self) -> RepairResult:
        return RepairResult(
            succeeded=False,
            final_value=None,
            attempts=self.attempts,
            total_attempts=len(self.attempts),
        )
