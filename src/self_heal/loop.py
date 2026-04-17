"""Core repair loop."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

from self_heal.diagnose import classify
from self_heal.llm import LLMProposer
from self_heal.propose import build_messages, extract_code
from self_heal.types import RepairAttempt, RepairResult

logger = logging.getLogger("self_heal")


_INSTALL_HINT = (
    "No LLM proposer configured and the default (ClaudeProposer) could not load.\n"
    "Install an LLM SDK:\n"
    "  pip install 'self-heal[claude]'     # Anthropic Claude (default)\n"
    "  pip install 'self-heal[openai]'     # OpenAI + OpenAI-compatible endpoints\n"
    "  pip install 'self-heal[gemini]'     # Google Gemini\n"
    "  pip install 'self-heal[litellm]'    # 100+ providers via LiteLLM\n"
    "Or pass your own: RepairLoop(proposer=MyProposer())"
)


class RepairLoop:
    """Iteratively repair a failing callable using an LLM.

    Example:
        loop = RepairLoop(model="claude-sonnet-4-6", max_attempts=3)
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

    def run(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> RepairResult:
        """Call `func(*args, **kwargs)`, repairing and retrying on failure."""
        kwargs = kwargs or {}
        current = func
        attempts: list[RepairAttempt] = []
        original_source = self._safe_source(func)

        for attempt_num in range(1, self.max_attempts + 1):
            try:
                value = current(*args, **kwargs)
            except Exception as exc:
                failure = classify(exc, {"args": list(args), "kwargs": kwargs})
                self._log(
                    f"Attempt {attempt_num} failed: {failure.error_type}: {failure.message}"
                )

                if attempt_num == self.max_attempts:
                    attempts.append(
                        RepairAttempt(
                            attempt_number=attempt_num,
                            failure=failure,
                            proposed_source=None,
                            succeeded=False,
                        )
                    )
                    break

                self._log("Proposing repair...")
                try:
                    system, user = build_messages(original_source, failure)
                    raw = self.proposer.propose(system, user)
                    proposed = extract_code(raw)
                    repaired = self._recompile(proposed, func.__name__, func)
                    attempts.append(
                        RepairAttempt(
                            attempt_number=attempt_num,
                            failure=failure,
                            proposed_source=proposed,
                            succeeded=False,
                        )
                    )
                    current = repaired
                    self._log("Repair applied, retrying...")
                except Exception as repair_exc:
                    self._log(f"Repair step itself failed: {repair_exc}")
                    attempts.append(
                        RepairAttempt(
                            attempt_number=attempt_num,
                            failure=failure,
                            proposed_source=None,
                            succeeded=False,
                            error_after_repair=str(repair_exc),
                        )
                    )
            else:
                if attempts:
                    attempts[-1].succeeded = True
                    self._log(f"Attempt {attempt_num} succeeded after repair.")
                return RepairResult(
                    succeeded=True,
                    final_value=value,
                    attempts=attempts,
                    total_attempts=attempt_num,
                )

        return RepairResult(
            succeeded=False,
            final_value=None,
            attempts=attempts,
            total_attempts=len(attempts),
        )

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
