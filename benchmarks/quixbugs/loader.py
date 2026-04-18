"""Load QuixBugs buggy programs as self-heal Tasks.

QuixBugs layout (from jkoppel/QuixBugs):
  python_programs/<name>.py          # buggy implementation
  correct_python_programs/<name>.py  # reference correct version
  json_testcases/<name>.json         # newline-delimited JSON: [inputs, expected]

Each line is `[inputs, expected]` where `inputs` is a list (sometimes
containing nested lists / dicts). For graph/tree programs the inputs are
serializable placeholders; these programs are skipped via `_SKIP`.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from benchmarks.tasks import Task

QUIXBUGS_REPO = "https://github.com/jkoppel/QuixBugs.git"

# Programs whose JSON testcases use non-trivial object placeholders
# (Node, Tree, WeightedGraph). These need custom deserialization; skip
# for the initial integration.
_SKIP: frozenset[str] = frozenset(
    {
        "breadth_first_search",
        "depth_first_search",
        "detect_cycle",
        "minimum_spanning_tree",
        "reverse_linked_list",
        "shortest_path_length",
        "shortest_path_lengths",
        "shortest_paths",
        "topological_ordering",
    }
)


def _cache_dir() -> Path:
    override = os.environ.get("SELF_HEAL_QUIXBUGS_DIR")
    if override:
        return Path(override)
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "self-heal" / "quixbugs"


def _ensure_clone(dest: Path) -> Path:
    """Clone QuixBugs into `dest` if not already present. Returns dest."""
    if (dest / "python_programs").exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", QUIXBUGS_REPO, str(dest)],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except FileNotFoundError as err:
        raise RuntimeError(
            "git is required to download QuixBugs but was not found on PATH"
        ) from err
    except subprocess.CalledProcessError as err:
        raise RuntimeError(
            f"git clone of QuixBugs failed: "
            f"{err.stderr.decode('utf-8', errors='replace')}"
        ) from err
    return dest


def _read_testcases(path: Path) -> list[tuple[list, object]]:
    """Parse a QuixBugs json_testcases/*.json file (newline-delimited JSON)."""
    cases: list[tuple[list, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, list) or len(record) != 2:
            continue
        inputs, expected = record
        if not isinstance(inputs, list):
            inputs = [inputs]
        cases.append((inputs, expected))
    return cases


def _make_test(
    case_inputs: list, expected: object, timeout: float = 5.0
) -> Callable:
    """Build a test that calls fn(*inputs) and asserts the expected value.

    Some QuixBugs bugs (notably `bitcount` with `n ^= n - 1`) produce
    infinite loops on certain inputs. We run the call in a daemon thread
    with a timeout so the benchmark stays forward-progressing even when
    the buggy source hangs. The hung thread is abandoned (daemon) — it
    keeps a CPU busy until the interpreter exits, but does not block the
    harness.
    """
    import threading

    def test(fn):
        result_holder: list = []
        exc_holder: list = []

        def call() -> None:
            try:
                value = fn(*case_inputs)
                try:
                    iter(value)
                    if not isinstance(value, (str, bytes, list, tuple, dict, set)):
                        value = list(value)
                except TypeError:
                    pass
                result_holder.append(value)
            except BaseException as err:
                exc_holder.append(err)

        t = threading.Thread(target=call, daemon=True)
        t.start()
        t.join(timeout=timeout)
        if t.is_alive():
            raise AssertionError(
                f"timeout after {timeout}s on inputs={case_inputs!r}"
            )
        if exc_holder:
            raise exc_holder[0]
        if not result_holder:
            raise AssertionError("no result produced")
        got = result_holder[0]
        assert got == expected, (
            f"inputs={case_inputs!r} expected={expected!r} got={got!r}"
        )

    test.__name__ = "quixbugs_case"
    return test


def load_quixbugs_tasks(
    cache_dir: Path | None = None,
    max_tests_per_task: int = 5,
) -> list[Task]:
    """Return QuixBugs programs as Tasks. Clones the repo on first call."""
    root = _ensure_clone(cache_dir or _cache_dir())
    programs_dir = root / "python_programs"
    testcases_dir = root / "json_testcases"

    tasks: list[Task] = []
    for py_file in sorted(programs_dir.glob("*.py")):
        name = py_file.stem
        if name in _SKIP or name.startswith("_") or name == "node":
            continue

        tc_file = testcases_dir / f"{name}.json"
        if not tc_file.exists():
            continue

        buggy_source = py_file.read_text(encoding="utf-8")
        # QuixBugs programs are a single `def <name>(...)` plus optional
        # auxiliary helpers. We want the primary function name to match
        # the file stem (QuixBugs convention).
        cases = _read_testcases(tc_file)
        if not cases:
            continue

        tests = [
            _make_test(inputs, expected)
            for inputs, expected in cases[:max_tests_per_task]
        ]
        tasks.append(
            Task(
                name=f"qb_{name}",
                description=f"QuixBugs: {name}",
                buggy_source=buggy_source,
                function_name=name,
                tests=tests,
            )
        )
    return tasks
