"""Write a repaired function back to its source file.

Prefers libcst (AST-faithful, handles decorators + multi-line signatures).
Falls back to textual replacement when libcst isn't installed.

Shared by the `self-heal heal --apply` CLI and the pytest plugin's
`--heal-apply`.
"""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

__all__ = [
    "PatchError",
    "apply_function_patch",
    "is_git_dirty",
]


class PatchError(RuntimeError):
    """Raised when the patch cannot be applied safely."""


def apply_function_patch(
    src_path: Path,
    fn_name: str,
    original_source: str,
    repaired_source: str,
    backup: bool = True,
) -> Path:
    """Replace `fn_name` in `src_path` with `repaired_source`.

    Returns the backup path if one was written, else the src_path itself.
    Raises PatchError on unrecoverable problems.
    """
    if not src_path.exists():
        raise PatchError(f"file not found: {src_path}")

    backup_path = src_path.with_suffix(src_path.suffix + ".heal-backup")
    if backup:
        shutil.copy2(src_path, backup_path)

    text = src_path.read_text(encoding="utf-8")
    new_text = _try_libcst(text, fn_name, repaired_source)
    if new_text is None:
        new_text = _textual_replace(text, original_source, repaired_source)
    if new_text is None:
        raise PatchError(
            f"could not locate function '{fn_name}' in {src_path} "
            f"for replacement"
        )

    src_path.write_text(new_text, encoding="utf-8")
    return backup_path if backup else src_path


def is_git_dirty(path: Path) -> bool:
    """Return True if `path` is git-tracked AND has uncommitted changes,
    OR if the git state could not be determined (fail-closed).

    Three real outcomes:
      - git says clean -> False
      - git says dirty -> True
      - git is unavailable (FileNotFoundError) -> False (not in a repo)
      - git timed out, errored, or returned non-zero -> True (unknown
        state treated as dirty so callers refuse to overwrite)
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", str(path)],
            capture_output=True,
            text=True,
            cwd=path.parent,
            timeout=10,
        )
    except FileNotFoundError:
        # git binary not installed; treat as "not in a repo" so the
        # plugin can still apply patches outside git.
        return False
    except subprocess.TimeoutExpired:
        # git hung (lock contention, AV scan, etc.). We cannot confirm
        # clean state, so fail closed: caller sees "dirty" and refuses
        # to modify the file without --heal-apply-force.
        return True
    if proc.returncode != 0:
        # Unknown git error; fail closed.
        return True
    return bool(proc.stdout.strip())


def _try_libcst(source_text: str, fn_name: str, repaired_source: str) -> str | None:
    """Replace `fn_name` in `source_text` using libcst. Returns None on
    failure (library missing, function not found, etc.)."""
    try:
        import libcst as cst
    except ImportError:
        return None

    try:
        module = cst.parse_module(source_text)
    except Exception:
        return None

    repaired_dedented = textwrap.dedent(repaired_source).strip() + "\n"
    try:
        new_fn_module = cst.parse_module(repaired_dedented)
    except Exception:
        return None

    new_fn_node: cst.FunctionDef | None = None
    for stmt in new_fn_module.body:
        if isinstance(stmt, cst.FunctionDef) and stmt.name.value == fn_name:
            new_fn_node = stmt
            break
    if new_fn_node is None:
        return None

    class _Replace(cst.CSTTransformer):
        def __init__(self):
            self.replaced = False

        def leave_FunctionDef(self, original, updated):
            if updated.name.value == fn_name and not self.replaced:
                self.replaced = True
                return new_fn_node
            return updated

    transformer = _Replace()
    new_module = module.visit(transformer)
    if not transformer.replaced:
        return None
    return new_module.code


def _textual_replace(
    source_text: str, original_source: str, repaired_source: str
) -> str | None:
    """Best-effort textual swap: find the original block, replace it.

    Tries the source as-given first, then a dedented variant (common
    when `inspect.getsource` returned an indented method body). Returns
    None if neither matches.
    """
    if original_source and original_source in source_text:
        return source_text.replace(original_source, repaired_source, 1)

    dedented_original = textwrap.dedent(original_source)
    dedented_repaired = textwrap.dedent(repaired_source)
    if dedented_original and dedented_original in source_text:
        return source_text.replace(dedented_original, dedented_repaired, 1)

    return None
