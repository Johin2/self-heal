"""Command-line interface for self-heal.

Two subcommands:

    self-heal heal FILE::FUNCTION [--test TEST] [--apply]
        Repair a specific function. Optionally apply the fix back to the
        file on disk.

    self-heal bench [--proposer claude|openai|gemini|litellm] [--model ...]
        Run the benchmark harness from `benchmarks/`.

Examples
--------
    self-heal heal mymod.py::extract_price --test tests/test_mymod.py::test_rupees
    self-heal heal mymod.py::extract_price --apply --proposer openai --model gpt-5
    self-heal bench --proposer gemini --model gemini-2.5-flash
"""

from __future__ import annotations

import argparse
import contextlib
import difflib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="self-heal",
        description="Automatic repair for failing Python code.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # heal subcommand
    p_heal = sub.add_parser("heal", help="Repair one function.")
    p_heal.add_argument(
        "target",
        help="`path/to/file.py::function_name`",
    )
    p_heal.add_argument(
        "--test",
        action="append",
        default=[],
        help="Test reference `path/to/test.py::test_function`. Can be passed "
        "multiple times. If omitted, self-heal only repairs raised exceptions.",
    )
    p_heal.add_argument(
        "--proposer",
        default="claude",
        choices=["claude", "openai", "gemini", "litellm"],
    )
    p_heal.add_argument("--model", default=None)
    p_heal.add_argument("--attempts", type=int, default=3)
    p_heal.add_argument(
        "--apply",
        action="store_true",
        help="Write the proposed fix back to the source file.",
    )
    p_heal.add_argument(
        "--safety",
        default="moderate",
        choices=["off", "moderate", "strict"],
    )

    # bench subcommand
    p_bench = sub.add_parser("bench", help="Run the benchmark harness.")
    p_bench.add_argument("--proposer", default="claude")
    p_bench.add_argument("--model", default=None)
    p_bench.add_argument("--attempts", type=int, default=3)
    p_bench.add_argument("--tasks", default=None)

    args = parser.parse_args(argv)

    if args.cmd == "heal":
        return _cmd_heal(args)
    if args.cmd == "bench":
        return _cmd_bench(args)
    return 1


# ---------------------------------------------------------------------------
# heal
# ---------------------------------------------------------------------------


def _cmd_heal(args) -> int:
    file_part, _, fn_name = args.target.partition("::")
    if not file_part or not fn_name:
        print("target must be 'path/to/file.py::function_name'", file=sys.stderr)
        return 2

    src_path = Path(file_part).resolve()
    if not src_path.exists():
        print(f"file not found: {src_path}", file=sys.stderr)
        return 2

    module = _load_module_from_path(src_path)
    target_fn = getattr(module, fn_name, None)
    if target_fn is None:
        print(f"function '{fn_name}' not found in {src_path}", file=sys.stderr)
        return 2

    test_callables = []
    for ref in args.test:
        t_file, _, t_name = ref.partition("::")
        if not t_file or not t_name:
            print(f"invalid --test {ref!r}", file=sys.stderr)
            return 2
        t_mod = _load_module_from_path(Path(t_file).resolve())
        t_fn = getattr(t_mod, t_name, None)
        if t_fn is None:
            print(f"test '{t_name}' not found in {t_file}", file=sys.stderr)
            return 2
        test_callables.append(_wrap_pytest_test(module, fn_name, t_fn))

    proposer = _make_proposer(args.proposer, args.model)
    from self_heal import RepairLoop
    from self_heal.safety import SafetyConfig

    loop = RepairLoop(
        max_attempts=args.attempts,
        proposer=proposer,
        safety=SafetyConfig(level=args.safety),
        verbose=True,
    )
    result = loop.run(target_fn, tests=test_callables or None)

    if not result.succeeded:
        print(
            f"\n✗ self-heal could not repair {args.target} after "
            f"{result.total_attempts} attempts",
            file=sys.stderr,
        )
        if result.attempts:
            last = result.attempts[-1].failure
            print(f"  last failure: {last.error_type}: {last.message}", file=sys.stderr)
        return 1

    winning = next(
        (a.proposed_source for a in reversed(result.attempts) if a.proposed_source),
        None,
    )
    if winning is None:
        print(f"\n✓ {args.target} already passes; no repair needed.")
        return 0

    original_source = inspect.getsource(target_fn)
    print(f"\n✓ repaired {args.target} in {result.total_attempts} attempts\n")
    print(_format_diff(original_source, winning))

    if args.apply:
        _apply_patch(src_path, fn_name, original_source, winning)
        print(f"\nApplied patch to {src_path}.")

    return 0


# ---------------------------------------------------------------------------
# bench
# ---------------------------------------------------------------------------


def _cmd_bench(args) -> int:
    # Delegate to the existing benchmark script.
    sys.argv = ["benchmarks/run.py"]
    if args.proposer:
        sys.argv += ["--proposer", args.proposer]
    if args.model:
        sys.argv += ["--model", args.model]
    if args.attempts:
        sys.argv += ["--attempts", str(args.attempts)]
    if args.tasks:
        sys.argv += ["--tasks", args.tasks]

    sys.path.insert(0, str(Path.cwd()))
    try:
        from benchmarks.run import main as bench_main  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        print(
            "benchmarks/ not found. Run this from a self-heal checkout, or "
            "copy benchmarks/ to your project.",
            file=sys.stderr,
        )
        return 2
    return bench_main()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _load_module_from_path(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = mod
    spec.loader.exec_module(mod)
    return mod


def _wrap_pytest_test(module, fn_name: str, test_fn):
    """Wrap a pytest-style test so self-heal can use it as a verifier.

    Replaces the target function wherever it is bound in the running
    interpreter (not just in its defining module), runs the test, then
    restores the original references.
    """
    original = getattr(module, fn_name)

    def verify(candidate_fn):
        patched: list[tuple[Any, Any]] = []
        for mod in list(sys.modules.values()):
            if mod is None:
                continue
            try:
                if getattr(mod, fn_name, None) is original:
                    patched.append((mod, original))
                    setattr(mod, fn_name, candidate_fn)
            except (AttributeError, ImportError):
                continue
        try:
            test_fn()
        finally:
            for mod, orig in patched:
                with contextlib.suppress(Exception):
                    setattr(mod, fn_name, orig)

    verify.__name__ = getattr(test_fn, "__name__", "pytest_test")
    return verify


def _make_proposer(kind: str, model: str | None):
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
            raise SystemExit("--model is required for --proposer litellm")
        return LiteLLMProposer(model=model)
    raise SystemExit(f"unknown proposer: {kind}")


def _format_diff(before: str, after: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile="original",
            tofile="proposed",
            lineterm="",
        )
    )


def _apply_patch(
    src_path: Path, fn_name: str, original_source: str, repaired_source: str
) -> None:
    """Replace the function definition in the file with the repaired source.

    Naive text-based replacement. If the original source appears verbatim in
    the file, we swap it for the repaired version. Otherwise we fall back to
    appending the repaired function at the end.
    """
    text = src_path.read_text(encoding="utf-8")
    if original_source in text:
        new_text = text.replace(original_source, repaired_source, 1)
    else:
        # Dedent the original, try again.
        dedented = _dedent(original_source)
        if dedented and dedented in text:
            new_text = text.replace(dedented, _dedent(repaired_source), 1)
        else:
            new_text = text.rstrip() + "\n\n\n# --- self-heal repaired ---\n" + repaired_source + "\n"
            print(
                f"warning: could not locate original {fn_name} in {src_path}; "
                "appended repaired version at the end.",
                file=sys.stderr,
            )
    src_path.write_text(new_text, encoding="utf-8")


def _dedent(s: str) -> str:
    import textwrap

    return textwrap.dedent(s)


if __name__ == "__main__":
    raise SystemExit(main())
