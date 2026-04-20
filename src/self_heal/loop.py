"""Core repair loop (sync + async)."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable
from typing import Any

from self_heal.cache import RepairCache
from self_heal.diagnose import classify
from self_heal.events import EventCallback, RepairEvent, emit
from self_heal.llm import LLMProposer
from self_heal.propose import build_messages, extract_code
from self_heal.safety import SafetyConfig, UnsafeProposalError, validate
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

    Each call to run() or arun() attempts to fix the function up to
    max_attempts times, using an LLM to propose new source code after
    each failure.

    Example::

        from self_heal import RepairLoop

        def flaky(x):
            return x / 0          # ZeroDivisionError on first call

        loop = RepairLoop(max_attempts=3)
        result = loop.run(flaky, args=(4,), verify=lambda v: v == 2)
        print(result.succeeded)   # True (after LLM patches the function)

    Optional features:

    * **cache** - pass a :class:`RepairCache` to skip the LLM when the same
      error has been seen and fixed before.
    * **safety** - pass a :class:`SafetyConfig` to validate proposed code
      before it is executed, optionally running it in a subprocess sandbox.
    * **on_event** - pass an :class:`EventCallback` to receive structured
      :class:`RepairEvent` objects as the loop progresses (useful for
      logging, progress UIs, and streaming token display).
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        max_attempts: int = 3,
        proposer: LLMProposer | None = None,
        verbose: bool = False,
        cache: RepairCache | None = None,
        safety: SafetyConfig | None = None,
        on_event: EventCallback | None = None,
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.max_attempts = max_attempts
        self.verbose = verbose
        self._model = model
        self._proposer: LLMProposer | None = proposer
        self.cache = cache
        self.safety = safety
        self.on_event = on_event

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

    # ----- Public runners -----

    def run(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict | None = None,
        verify: Verifier | None = None,
        tests: list[Test] | None = None,
        prompt_extra: str | None = None,
    ) -> RepairResult:
        """Sync: call `func(*args, **kwargs)`, repairing until it succeeds."""
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
            emit(self.on_event, RepairEvent("attempt_start", attempt_number=attempt_num))
            result, finished = ctx.try_call(attempt_num)
            if finished:
                emit(self.on_event, RepairEvent("repair_succeeded", attempt_number=attempt_num))
                return result

            if attempt_num == self.max_attempts:
                emit(self.on_event, RepairEvent("repair_exhausted", attempt_number=attempt_num))
                return ctx.final_failure()

            raw = self._obtain_repair(ctx)
            ctx.apply_proposal(raw, attempt_num)

        emit(self.on_event, RepairEvent("repair_exhausted"))
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
        """Async variant of `run`."""
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
            emit(self.on_event, RepairEvent("attempt_start", attempt_number=attempt_num))
            result, finished = await ctx.atry_call(attempt_num)
            if finished:
                emit(self.on_event, RepairEvent("repair_succeeded", attempt_number=attempt_num))
                return result

            if attempt_num == self.max_attempts:
                emit(self.on_event, RepairEvent("repair_exhausted", attempt_number=attempt_num))
                return ctx.final_failure()

            raw = await self._aobtain_repair(ctx)
            ctx.apply_proposal(raw, attempt_num)

        emit(self.on_event, RepairEvent("repair_exhausted"))
        return ctx.final_failure()

    # ----- Internals -----

    def _obtain_repair(self, ctx: _RunContext) -> str:
        """Ask the LLM for a repaired version of the failing function (sync).

        Checks the cache first. If the proposer supports streaming and an
        on_event callback is registered, emits propose_chunk events for each
        delta. If streaming fails, emits a stream_error event and falls back
        to the regular propose() call.

        Returns the raw LLM response string.
        """
        if self.cache is not None:
            hit = self.cache.lookup(ctx.original_source, ctx.last_failure)
            if hit is not None:
                self._log("Cache hit - skipping LLM.")
                emit(self.on_event, RepairEvent("cache_hit"))
                return hit
            emit(self.on_event, RepairEvent("cache_miss"))

        self._log("Proposing repair...")
        emit(self.on_event, RepairEvent("propose_start"))
        system, user = build_messages(
            ctx.original_source,
            ctx.last_failure,
            history=list(ctx.attempts),
            extra=ctx.prompt_extra,
        )

        proposer = self.proposer
        if hasattr(proposer, "propose_stream") and self.on_event is not None:
            chunks: list[str] = []
            try:
                for delta in proposer.propose_stream(system, user):
                    chunks.append(delta)
                    emit(self.on_event, RepairEvent("propose_chunk", delta=delta))
                raw = "".join(chunks)
            except Exception as stream_exc:
                emit(self.on_event, RepairEvent("stream_error", error=str(stream_exc)))
                raw = proposer.propose(system, user)
        else:
            raw = proposer.propose(system, user)

        emit(
            self.on_event,
            RepairEvent("propose_complete", proposed_source=extract_code(raw)),
        )
        return raw

    async def _aobtain_repair(self, ctx: _RunContext) -> str:
        """Async version of _obtain_repair.

        Prefers apropose_stream if available, then apropose, then falls back
        to running the sync propose() in a thread via asyncio.to_thread.
        Emits stream_error if async streaming raises an exception.

        Returns the raw LLM response string.
        """
        if self.cache is not None:
            hit = self.cache.lookup(ctx.original_source, ctx.last_failure)
            if hit is not None:
                self._log("Cache hit - skipping LLM.")
                emit(self.on_event, RepairEvent("cache_hit"))
                return hit
            emit(self.on_event, RepairEvent("cache_miss"))

        self._log("Proposing repair...")
        emit(self.on_event, RepairEvent("propose_start"))
        system, user = build_messages(
            ctx.original_source,
            ctx.last_failure,
            history=list(ctx.attempts),
            extra=ctx.prompt_extra,
        )

        proposer = self.proposer
        if hasattr(proposer, "apropose_stream") and self.on_event is not None:
            chunks: list[str] = []
            try:
                async for delta in proposer.apropose_stream(system, user):
                    chunks.append(delta)
                    emit(self.on_event, RepairEvent("propose_chunk", delta=delta))
                raw = "".join(chunks)
            except Exception as stream_exc:
                emit(self.on_event, RepairEvent("stream_error", error=str(stream_exc)))
                raw = await self._acall_propose(proposer, system, user)
        else:
            raw = await self._acall_propose(proposer, system, user)

        emit(
            self.on_event,
            RepairEvent("propose_complete", proposed_source=extract_code(raw)),
        )
        return raw

    @staticmethod
    async def _acall_propose(proposer, system: str, user: str) -> str:
        if hasattr(proposer, "apropose"):
            return await proposer.apropose(system, user)
        return await asyncio.to_thread(proposer.propose, system, user)

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
    """Holds all mutable state for a single run() or arun() call.

    Keeps track of the original function, the current (possibly repaired)
    version, the list of attempts so far, and the last recorded failure.
    Shared between the sync and async code paths.
    """

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
        self.last_failure = None

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

        if self.attempts:
            self.attempts[-1].succeeded = True
            self.loop._log(f"Attempt {attempt_num} succeeded after repair.")
            if self.loop.cache is not None and self.attempts[-1].proposed_source:
                self.loop.cache.record(
                    self.original_source,
                    self.attempts[-1].failure,
                    self.attempts[-1].proposed_source,
                    succeeded=True,
                )
            emit(
                self.loop.on_event,
                RepairEvent("verify_success", attempt_number=attempt_num),
            )

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
        self.attempts.append(
            RepairAttempt(
                attempt_number=attempt_num,
                failure=failure,
                proposed_source=None,
                succeeded=False,
            )
        )
        emit(
            self.loop.on_event,
            RepairEvent("attempt_failed", attempt_number=attempt_num, failure=failure),
        )

    def apply_proposal(self, raw: str, attempt_num: int) -> None:
        try:
            proposed = extract_code(raw)
            # Safety check before exec.
            if self.loop.safety is not None:
                try:
                    validate(proposed, self.loop.safety)
                except UnsafeProposalError as safety_err:
                    self.loop._log(f"Proposal rejected by safety rails: {safety_err}")
                    self.attempts[-1].error_after_repair = f"safety: {safety_err}"
                    emit(
                        self.loop.on_event,
                        RepairEvent("safety_violation", error=str(safety_err)),
                    )
                    return
            if (
                self.loop.safety is not None
                and self.loop.safety.sandbox == "subprocess"
            ):
                from self_heal.sandbox import (
                    SubprocessSandbox,
                    make_sandboxed_callable,
                )

                sb = SubprocessSandbox(timeout=self.loop.safety.sandbox_timeout)
                repaired = make_sandboxed_callable(
                    proposed, self.original.__name__, sb
                )
            else:
                repaired = RepairLoop._recompile(
                    proposed, self.original.__name__, self.original
                )
        except Exception as repair_exc:
            self.loop._log(f"Repair step itself failed: {repair_exc}")
            self.attempts[-1].error_after_repair = str(repair_exc)
            emit(
                self.loop.on_event,
                RepairEvent("install_failed", error=str(repair_exc)),
            )
            # Record the failed cache entry so we don't serve it again.
            if self.loop.cache is not None:
                self.loop.cache.record(
                    self.original_source,
                    self.last_failure,
                    proposed if "proposed" in locals() else raw,
                    succeeded=False,
                )
            return

        self.attempts[-1].proposed_source = proposed
        self.current = repaired
        self.loop._log("Repair applied, retrying...")
        emit(
            self.loop.on_event,
            RepairEvent("install_success", proposed_source=proposed),
        )

    def final_failure(self) -> RepairResult:
        return RepairResult(
            succeeded=False,
            final_value=None,
            attempts=self.attempts,
            total_attempts=len(self.attempts),
        )
