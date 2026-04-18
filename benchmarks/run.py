"""Benchmark self-heal vs naive single-shot repair.

For each task:
  - load the buggy function
  - run two strategies:
      (A) naive single-shot: propose once (no history), try once
      (B) self-heal full:    multi-turn with history, tests-driven
  - record pass/fail

Usage:
    python benchmarks/run.py                              # Claude (default)
    python benchmarks/run.py --proposer openai --model gpt-5
    python benchmarks/run.py --proposer gemini --model gemini-2.5-flash
    python benchmarks/run.py --proposer litellm --model groq/llama-3.3-70b-versatile
    python benchmarks/run.py --attempts 5 --tasks extract_price,flatten

Set the matching API key (ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY).
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Any

# Allow running as `python benchmarks/run.py` from repo root.
sys.path.insert(0, ".")
sys.path.insert(0, "src")

from benchmarks.tasks import TASKS, Task  # noqa: E402
from self_heal.llm import LLMProposer  # noqa: E402
from self_heal.propose import build_messages, extract_code  # noqa: E402
from self_heal.verify import check_tests  # noqa: E402

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


@dataclass
class Outcome:
    passed: bool
    attempts_used: int
    llm_calls: int
    error: str | None = None


def _compile_fn(source: str, name: str):
    namespace: dict[str, Any] = {}
    exec(source, namespace)  # noqa: S102
    return namespace[name]


def run_naive(task: Task, proposer: LLMProposer) -> Outcome:
    """Single-shot repair: build one prompt (no history), recompile, test once."""
    original_fn = _compile_fn(task.buggy_source, task.function_name)

    # Catch the FIRST test failure to feed the proposer.
    failure = check_tests(original_fn, task.tests)
    if failure is None:
        return Outcome(passed=True, attempts_used=1, llm_calls=0)

    try:
        system, user = build_messages(task.buggy_source, failure, history=None)
        raw = proposer.propose(system, user)
        proposed = extract_code(raw)
        repaired_fn = _compile_fn(proposed, task.function_name)
    except Exception as exc:
        return Outcome(passed=False, attempts_used=1, llm_calls=1, error=str(exc))

    # One retry with the proposed repair.
    post = check_tests(repaired_fn, task.tests)
    return Outcome(
        passed=(post is None),
        attempts_used=2,
        llm_calls=1,
        error=(post.message if post else None),
    )


def run_self_heal(
    task: Task, proposer: LLMProposer, max_attempts: int
) -> Outcome:
    """Full self-heal: multi-turn repair with history + test-driven verification.

    Mirrors RepairLoop's logic but driven purely by the task's tests, since
    these tasks don't have a natural call-signature to pass through.
    """
    current_fn = _compile_fn(task.buggy_source, task.function_name)
    attempts: list = []
    last_failure = None
    llm_calls = 0

    for attempt_num in range(1, max_attempts + 1):
        failure = check_tests(current_fn, task.tests)
        if failure is None:
            return Outcome(
                passed=True, attempts_used=attempt_num, llm_calls=llm_calls
            )

        last_failure = failure
        if attempt_num == max_attempts:
            break

        try:
            system, user = build_messages(
                task.buggy_source,
                failure,
                history=attempts,
            )
            raw = proposer.propose(system, user)
            llm_calls += 1
            proposed = extract_code(raw)
            new_fn = _compile_fn(proposed, task.function_name)
        except Exception as exc:
            from self_heal.types import RepairAttempt

            attempts.append(
                RepairAttempt(
                    attempt_number=attempt_num,
                    failure=failure,
                    proposed_source=None,
                    succeeded=False,
                    error_after_repair=str(exc),
                )
            )
            continue

        from self_heal.types import RepairAttempt

        attempts.append(
            RepairAttempt(
                attempt_number=attempt_num,
                failure=failure,
                proposed_source=proposed,
                succeeded=False,
            )
        )
        current_fn = new_fn

    return Outcome(
        passed=False,
        attempts_used=max_attempts,
        llm_calls=llm_calls,
        error=(last_failure.message if last_failure else None),
    )


# ---------------------------------------------------------------------------
# Proposer factory
# ---------------------------------------------------------------------------


def make_proposer(kind: str, model: str | None) -> LLMProposer:
    if kind == "claude":
        from self_heal.llm import ClaudeProposer

        return ClaudeProposer(model=model or "claude-sonnet-4-6")
    if kind == "openai":
        from self_heal.llm import OpenAIProposer

        return OpenAIProposer(model=model or "gpt-4o-mini")
    if kind == "gemini":
        from self_heal.llm import GeminiProposer

        return GeminiProposer(model=model or "gemini-2.5-flash")
    if kind == "litellm":
        from self_heal.llm import LiteLLMProposer

        if not model:
            raise SystemExit("--model is required for litellm proposer")
        return LiteLLMProposer(model=model)
    raise SystemExit(f"unknown proposer kind: {kind}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="self-heal benchmark")
    parser.add_argument(
        "--proposer",
        default="claude",
        choices=["claude", "openai", "gemini", "litellm"],
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument(
        "--tasks", default=None, help="comma-separated task names; default = all"
    )
    parser.add_argument(
        "--suite",
        default="default",
        choices=["default", "quixbugs"],
        help="which task suite to run: 'default' (hand-written) or 'quixbugs' "
        "(QuixBugs repair benchmark, clones on first use)",
    )
    args = parser.parse_args()

    proposer = make_proposer(args.proposer, args.model)

    if args.suite == "quixbugs":
        from benchmarks.quixbugs import load_quixbugs_tasks

        try:
            selected = load_quixbugs_tasks()
        except RuntimeError as exc:
            print(f"failed to load QuixBugs: {exc}", file=sys.stderr)
            return 2
    else:
        selected = TASKS
    if args.tasks:
        wanted = {t.strip() for t in args.tasks.split(",")}
        selected = [t for t in TASKS if t.name in wanted]
        missing = wanted - {t.name for t in selected}
        if missing:
            print(f"Unknown tasks: {sorted(missing)}", file=sys.stderr)
            return 2

    print(
        f"\n{'Task':<20} {'Naive':<10} {'self-heal':<12} {'Naive calls':<12} "
        f"{'SH calls':<10} {'SH attempts':<12}"
    )
    print("-" * 80)

    wins_naive = 0
    wins_sh = 0
    total_naive_calls = 0
    total_sh_calls = 0

    for task in selected:
        t0 = time.time()
        naive = run_naive(task, proposer)
        sh = run_self_heal(task, proposer, args.attempts)
        elapsed = time.time() - t0

        wins_naive += int(naive.passed)
        wins_sh += int(sh.passed)
        total_naive_calls += naive.llm_calls
        total_sh_calls += sh.llm_calls

        naive_mark = "PASS" if naive.passed else "FAIL"
        sh_mark = "PASS" if sh.passed else "FAIL"
        print(
            f"{task.name:<20} {naive_mark:<10} {sh_mark:<12} "
            f"{naive.llm_calls:<12} {sh.llm_calls:<10} "
            f"{sh.attempts_used:<12} ({elapsed:.1f}s)"
        )

    n = len(selected)
    print("-" * 80)
    print(f"\nProposer: {args.proposer} ({args.model or 'default'})")
    print(f"Tasks:    {n}")
    print(f"Naive single-shot: {wins_naive}/{n}  ({100 * wins_naive / n:.0f}%)")
    print(f"self-heal full:    {wins_sh}/{n}  ({100 * wins_sh / n:.0f}%)")
    print(f"Delta:             +{wins_sh - wins_naive} tasks")
    print(f"LLM calls — naive: {total_naive_calls}, self-heal: {total_sh_calls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
