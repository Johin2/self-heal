"""Tests for the QuixBugs benchmark loader.

We don't hit the network. The test points SELF_HEAL_QUIXBUGS_DIR at a
fake QuixBugs checkout in tmp_path.
"""

from __future__ import annotations

import textwrap

from benchmarks.quixbugs.loader import load_quixbugs_tasks


def _write_fake_quixbugs(root) -> None:
    (root / "python_programs").mkdir(parents=True)
    (root / "correct_python_programs").mkdir(parents=True)
    (root / "json_testcases").mkdir(parents=True)

    (root / "python_programs" / "bitcount.py").write_text(
        textwrap.dedent(
            """
            def bitcount(n):
                count = 0
                while n:
                    n ^= n - 1
                    count += 1
                return count
            """
        ).lstrip(),
        encoding="utf-8",
    )
    (root / "json_testcases" / "bitcount.json").write_text(
        "[[127], 7]\n[[128], 1]\n[[3005], 9]\n",
        encoding="utf-8",
    )

    # A task we should skip (graph algorithms)
    (root / "python_programs" / "detect_cycle.py").write_text(
        "def detect_cycle(node):\n    return False\n", encoding="utf-8"
    )
    (root / "json_testcases" / "detect_cycle.json").write_text(
        "[[], false]\n", encoding="utf-8"
    )


def test_loader_adapts_programs_into_tasks(tmp_path, monkeypatch):
    _write_fake_quixbugs(tmp_path)
    monkeypatch.setenv("SELF_HEAL_QUIXBUGS_DIR", str(tmp_path))

    tasks = load_quixbugs_tasks(cache_dir=tmp_path)
    names = {t.name for t in tasks}

    assert "qb_bitcount" in names
    # detect_cycle is in the skip list — must not appear
    assert "qb_detect_cycle" not in names

    bitcount = next(t for t in tasks if t.name == "qb_bitcount")
    assert bitcount.function_name == "bitcount"
    assert "def bitcount" in bitcount.buggy_source
    assert len(bitcount.tests) >= 2


def test_loader_tests_run_against_correct_impl(tmp_path):
    _write_fake_quixbugs(tmp_path)
    tasks = load_quixbugs_tasks(cache_dir=tmp_path)
    bitcount = next(t for t in tasks if t.name == "qb_bitcount")

    def correct_bitcount(n):
        return bin(n).count("1")

    for test in bitcount.tests:
        test(correct_bitcount)


def test_loader_tests_catch_a_wrong_implementation(tmp_path):
    """A deliberately-wrong bitcount should fail the generated tests.

    We don't run the actual QuixBugs buggy source here because several
    QuixBugs bugs (e.g. bitcount's `n ^= n - 1`) cause infinite loops
    on certain inputs, which would hang the test without a sandbox.
    """
    _write_fake_quixbugs(tmp_path)
    tasks = load_quixbugs_tasks(cache_dir=tmp_path)
    bitcount = next(t for t in tasks if t.name == "qb_bitcount")

    def always_zero(n):
        return 0

    failures = 0
    for test in bitcount.tests:
        try:
            test(always_zero)
        except AssertionError:
            failures += 1
    assert failures >= 1
