"""AST-based safety rails for LLM-proposed repairs.

LLM-generated code runs via `exec()` in the caller's process. This module
rejects proposals that do things we almost certainly didn't ask for:
spawning processes, opening sockets, touching the filesystem via `os`,
mucking with globals, or using `eval`/`exec`/`__import__` as escape hatches.

Three preset levels, plus full custom control:
    - "off"       : no checks (v0.1 behavior)
    - "moderate"  : block dangerous calls; allow stdlib imports  (default)
    - "strict"    : block all non-whitelisted imports
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

SafetyLevel = Literal["off", "moderate", "strict"]


# Always-blocked callables (even on "off" for very dangerous ones? No — off = off).
_BLOCKED_CALLABLES: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "breakpoint",
    }
)

# Attribute-access patterns that are escape hatches for the sandbox.
_BLOCKED_ATTRS: frozenset[str] = frozenset(
    {
        "__globals__",
        "__builtins__",
        "__code__",
        "__class__",
        "__mro__",
        "__subclasses__",
        "__bases__",
        "__dict__",
    }
)

# Modules that should never be imported by a "repair" — almost certainly
# not what the user wanted.
_BLOCKED_IMPORTS: frozenset[str] = frozenset(
    {
        "subprocess",
        "socket",
        "shutil",
        "pickle",
        "ctypes",
        "multiprocessing",
        "threading",
    }
)

# Sensitive modules: allowed at moderate (stdlib utilities) but specific
# calls within them are restricted below. `os` is the big one.
_SENSITIVE_MODULE_CALLS: frozenset[str] = frozenset(
    {
        "os.system",
        "os.popen",
        "os.exec",
        "os.execv",
        "os.execvp",
        "os.spawn",
        "os.spawnv",
        "os.remove",
        "os.unlink",
        "os.rmdir",
        "os.removedirs",
        "os.kill",
    }
)


SandboxMode = Literal["none", "subprocess"]


@dataclass
class SafetyConfig:
    level: SafetyLevel = "moderate"
    extra_allowed_imports: set[str] = field(default_factory=set)
    extra_blocked_imports: set[str] = field(default_factory=set)
    sandbox: SandboxMode = "none"
    sandbox_timeout: float = 30.0


class UnsafeProposalError(ValueError):
    """Raised when an LLM proposal fails AST safety checks."""


def validate(source: str, config: SafetyConfig | None = None) -> None:
    """Raise UnsafeProposalError if `source` violates the safety config."""
    cfg = config or SafetyConfig()
    if cfg.level == "off":
        return

    try:
        tree = ast.parse(source)
    except SyntaxError as err:
        raise UnsafeProposalError(f"proposal is not valid Python: {err}") from err

    issues: list[str] = []
    for node in ast.walk(tree):
        for issue in _inspect_node(node, cfg):
            issues.append(issue)

    if issues:
        raise UnsafeProposalError("unsafe proposal: " + "; ".join(issues))


def _inspect_node(node: ast.AST, cfg: SafetyConfig) -> Iterable[str]:
    # Blocked top-level callables: eval(), exec(), __import__(), ...
    if isinstance(node, ast.Call):
        name = _call_name(node.func)
        if name in _BLOCKED_CALLABLES:
            yield f"call to blocked builtin `{name}`"
        if name in _SENSITIVE_MODULE_CALLS:
            yield f"call to sensitive function `{name}`"

    # Blocked attribute access (introspection escape hatches)
    if isinstance(node, ast.Attribute) and node.attr in _BLOCKED_ATTRS:
        yield f"access to reserved attribute `{node.attr}`"

    # Global / nonlocal writes
    if isinstance(node, ast.Global):
        yield f"`global` statement for {', '.join(node.names)}"

    # Import checks
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        yield from _check_import(node, cfg)


def _check_import(
    node: ast.Import | ast.ImportFrom, cfg: SafetyConfig
) -> Iterable[str]:
    modules: list[str] = []
    if isinstance(node, ast.Import):
        modules = [alias.name.split(".")[0] for alias in node.names]
    else:
        if node.module:
            modules = [node.module.split(".")[0]]

    for mod in modules:
        if mod in cfg.extra_blocked_imports:
            yield f"import of explicitly-blocked module `{mod}`"
            continue
        if mod in _BLOCKED_IMPORTS:
            yield f"import of blocked module `{mod}`"
            continue

        if cfg.level == "strict":
            if mod in cfg.extra_allowed_imports:
                continue
            if not _is_stdlib_safe_for_strict(mod):
                yield f"strict mode forbids import of `{mod}`"


# A minimal whitelist of harmless stdlib modules allowed in strict mode.
_STRICT_ALLOWED_STDLIB: frozenset[str] = frozenset(
    {
        "math",
        "re",
        "string",
        "json",
        "collections",
        "itertools",
        "functools",
        "operator",
        "typing",
        "dataclasses",
        "enum",
        "decimal",
        "fractions",
        "datetime",
        "statistics",
        "bisect",
        "heapq",
        "array",
        "copy",
        "abc",
    }
)


def _is_stdlib_safe_for_strict(module: str) -> bool:
    return module in _STRICT_ALLOWED_STDLIB


def _call_name(node: ast.expr) -> str | None:
    """Best-effort dotted name for a callable expression."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        if base is None:
            return node.attr
        return f"{base}.{node.attr}"
    return None
