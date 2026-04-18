"""Tests for the source-patching helpers used by CLI --apply and
pytest --heal-apply."""

from __future__ import annotations

import subprocess
import textwrap

import pytest

from self_heal._patch import (
    PatchError,
    apply_function_patch,
    is_git_dirty,
)


def test_textual_replace_preserves_surrounding_code(tmp_path):
    src = tmp_path / "mymod.py"
    src.write_text(
        textwrap.dedent(
            '''
            """module doc"""

            def other():
                return 42


            def buggy(x):
                return x + x


            CONST = 99
            '''
        ).lstrip(),
        encoding="utf-8",
    )

    original = "def buggy(x):\n    return x + x\n"
    repaired = "def buggy(x):\n    return x * x\n"

    backup = apply_function_patch(src, "buggy", original, repaired)
    assert backup.exists()
    assert backup.suffix == ".heal-backup"

    new_text = src.read_text(encoding="utf-8")
    assert "return x * x" in new_text
    assert "return x + x" not in new_text
    assert "CONST = 99" in new_text  # didn't clobber surrounding code
    assert "def other():" in new_text


def test_apply_with_decorator_via_libcst_or_textual(tmp_path):
    """libcst is preferred but optional; the textual fallback should
    also handle simple decorated functions."""
    src = tmp_path / "mod.py"
    src.write_text(
        textwrap.dedent(
            '''
            def cache(fn):
                return fn

            @cache
            def greet(name):
                return "hi " + name
            '''
        ).lstrip(),
        encoding="utf-8",
    )

    original = '@cache\ndef greet(name):\n    return "hi " + name\n'
    repaired = '@cache\ndef greet(name):\n    return f"Hello, {name}!"\n'

    apply_function_patch(src, "greet", original, repaired)
    new_text = src.read_text(encoding="utf-8")
    assert "Hello, {name}" in new_text


def test_missing_target_raises_patch_error(tmp_path):
    src = tmp_path / "mod.py"
    src.write_text("def something():\n    return 1\n", encoding="utf-8")

    with pytest.raises(PatchError, match="could not locate"):
        apply_function_patch(
            src, "nonexistent",
            "def nonexistent():\n    return 0\n",
            "def nonexistent():\n    return 1\n",
        )


def test_is_git_dirty_detects_uncommitted_change(tmp_path):
    # Init a git repo, commit a clean file, then dirty it.
    repo = tmp_path / "repo"
    repo.mkdir()
    try:
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True, timeout=10)
        subprocess.run(
            ["git", "config", "user.email", "t@t.t"], cwd=repo, check=True, timeout=10
        )
        subprocess.run(
            ["git", "config", "user.name", "t"], cwd=repo, check=True, timeout=10
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git not available")

    f = repo / "m.py"
    f.write_text("def a():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "m.py"], cwd=repo, check=True, timeout=10)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"], cwd=repo, check=True, timeout=10
    )

    assert is_git_dirty(f) is False

    f.write_text("def a():\n    return 2\n", encoding="utf-8")
    assert is_git_dirty(f) is True


def test_apply_creates_backup_file(tmp_path):
    src = tmp_path / "x.py"
    original_text = "def f():\n    return 1\n"
    src.write_text(original_text, encoding="utf-8")

    backup = apply_function_patch(
        src, "f", "def f():\n    return 1\n", "def f():\n    return 2\n"
    )
    assert backup.read_text(encoding="utf-8") == original_text
    assert "return 2" in src.read_text(encoding="utf-8")
