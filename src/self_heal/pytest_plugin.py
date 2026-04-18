"""pytest plugin: heal failing tests' target functions.

Usage
-----

1. Enable at the CLI:

       pytest --heal

2. Mark tests that target a specific function:

       import pytest

       @pytest.mark.heal(target="mymodule.extract_price")
       def test_parses_rupees():
           from mymodule import extract_price
           assert extract_price("₹1,299") == 1299.0

3. When the test fails AND `--heal` is enabled, self-heal loads the
   target function's source, runs a repair loop using the test as
   verification, and prints the proposed fix at the end of the session.

This v0.2 plugin prints suggestions. Auto-applying patches to disk is
slated for v0.3 behind `--heal-apply`.
"""

from __future__ import annotations

import contextlib
import importlib
import inspect
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _HealCandidate:
    nodeid: str
    target: str
    test_callable: Any
    failure_message: str = ""


@dataclass
class _HealSession:
    enabled: bool = False
    apply: bool = False
    apply_force: bool = False
    candidates: list[_HealCandidate] = field(default_factory=list)


def pytest_addoption(parser) -> None:
    group = parser.getgroup("self-heal")
    group.addoption(
        "--heal",
        action="store_true",
        default=False,
        help="After failing tests marked with @pytest.mark.heal(target=...), "
        "run self-heal on the target function and print proposed fixes.",
    )
    group.addoption(
        "--heal-apply",
        action="store_true",
        default=False,
        help="Write accepted repairs back to disk (implies --heal). Creates "
        "a .py.heal-backup next to each modified file. Refuses to modify "
        "git-dirty files unless --heal-apply-force is given.",
    )
    group.addoption(
        "--heal-apply-force",
        action="store_true",
        default=False,
        help="Allow --heal-apply to modify files that have uncommitted "
        "changes. Use with care.",
    )


def pytest_configure(config) -> None:
    config.addinivalue_line(
        "markers",
        "heal(target): mark a test whose failure should trigger self-heal "
        "on the named target function (e.g. 'mymodule.myfunc').",
    )
    apply = bool(config.getoption("--heal-apply"))
    # --heal-apply implies --heal
    enabled = bool(config.getoption("--heal")) or apply
    config._self_heal_session = _HealSession(  # type: ignore[attr-defined]
        enabled=enabled,
        apply=apply,
        apply_force=bool(config.getoption("--heal-apply-force")),
    )


def pytest_runtest_makereport(item, call) -> None:
    if call.when != "call" or call.excinfo is None:
        return
    session: _HealSession = getattr(item.config, "_self_heal_session", None)
    if session is None or not session.enabled:
        return

    marker = item.get_closest_marker("heal")
    if marker is None:
        return
    target = marker.kwargs.get("target") or (marker.args[0] if marker.args else None)
    if not target:
        return

    session.candidates.append(
        _HealCandidate(
            nodeid=item.nodeid,
            target=target,
            test_callable=item.obj,
            failure_message=str(call.excinfo.value),
        )
    )


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    session: _HealSession = getattr(config, "_self_heal_session", None)
    if session is None or not session.enabled or not session.candidates:
        return

    tr = terminalreporter
    tr.write_sep("=", "self-heal: failing tests to heal", purple=True)

    for cand in session.candidates:
        tr.write_line(f"\n▸ {cand.nodeid}")
        tr.write_line(f"  target: {cand.target}")
        try:
            outcome = _heal_candidate(cand)
        except Exception as exc:  # noqa: BLE001
            tr.write_line(f"  ✗ could not heal: {exc}", red=True)
            continue
        if outcome is None:
            tr.write_line("  (no repair needed — target already passes test)")
            continue

        diff, original_source, repaired_source, src_path = outcome
        tr.write_line("  proposed repair:", green=True)
        for line in diff.splitlines():
            tr.write_line(f"    {line}")

        if session.apply:
            _apply_or_report(
                tr, cand, src_path, original_source, repaired_source,
                force=session.apply_force,
            )

    tr.write_sep("=", "self-heal: end", purple=True)


def _apply_or_report(
    tr, cand: _HealCandidate, src_path, original_source: str,
    repaired_source: str, force: bool,
) -> None:
    from self_heal._patch import PatchError, apply_function_patch, is_git_dirty

    if src_path is None:
        tr.write_line(
            f"  ✗ APPLY skipped: could not locate source file for {cand.target}",
            red=True,
        )
        return

    if not force and is_git_dirty(src_path):
        tr.write_line(
            f"  ✗ APPLY skipped: {src_path} has uncommitted changes "
            "(use --heal-apply-force to override)",
            red=True,
        )
        return

    _, _, fn_name = cand.target.rpartition(".")
    try:
        backup = apply_function_patch(
            src_path, fn_name, original_source, repaired_source
        )
    except PatchError as exc:
        tr.write_line(f"  ✗ APPLY failed: {exc}", red=True)
        return

    tr.write_line(
        f"  ✓ APPLIED to {src_path} (backup: {backup.name})", green=True
    )


def _heal_candidate(cand: _HealCandidate):
    """Run self-heal on the target function using this test.

    Returns a 4-tuple (diff_text, original_source, repaired_source, src_path),
    or None if no repair was needed.
    """

    import sys
    from pathlib import Path

    from self_heal import RepairLoop

    module_name, _, fn_name = cand.target.rpartition(".")
    if not module_name or not fn_name:
        raise ValueError(
            f"invalid target {cand.target!r}; expected 'module.function'"
        )

    module = importlib.import_module(module_name)
    target_fn = getattr(module, fn_name)
    original_source = inspect.getsource(target_fn)
    src_path: Path | None = None
    try:
        raw_file = inspect.getsourcefile(target_fn)
        if raw_file:
            src_path = Path(raw_file).resolve()
    except (OSError, TypeError):
        src_path = None
    test_body = cand.test_callable

    def verify_via_pytest_body(candidate_fn):
        # Patch every module that has a reference to the target function.
        # Top-level `from mod import fn` binds the original in the importer's
        # namespace; patching only `module.fn` would leave stale references.
        patched = []
        for mod in list(sys.modules.values()):
            if mod is None:
                continue
            try:
                if getattr(mod, fn_name, None) is target_fn:
                    patched.append(mod)
                    setattr(mod, fn_name, candidate_fn)
            except (AttributeError, ImportError):
                continue
        try:
            test_body()
        finally:
            for mod in patched:
                with contextlib.suppress(Exception):
                    setattr(mod, fn_name, target_fn)

    verify_via_pytest_body.__name__ = f"pytest::{cand.nodeid}"

    loop = RepairLoop(max_attempts=3)
    result = loop.run(target_fn, tests=[verify_via_pytest_body])

    if not result.succeeded:
        raise RuntimeError(
            f"self-heal could not repair {cand.target} after "
            f"{result.total_attempts} attempts"
        )

    # The last attempt's proposed_source is the winning repair.
    winning = next(
        (a.proposed_source for a in reversed(result.attempts) if a.proposed_source),
        None,
    )
    if winning is None:
        return None

    return (_format_diff(original_source, winning), original_source, winning, src_path)


def _format_diff(before: str, after: str) -> str:
    import difflib

    diff_lines = list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile="original",
            tofile="proposed",
            lineterm="",
        )
    )
    return "\n".join(diff_lines) if diff_lines else after
