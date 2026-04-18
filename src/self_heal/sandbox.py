"""Subprocess sandbox for running LLM-proposed repairs in isolation.

The default repair loop execs proposed source in the caller's process.
AST rails in `safety.py` block the obvious escape hatches, but a real
process boundary is a stronger guarantee.

Opt in via:

    from self_heal import SafetyConfig, repair

    @repair(safety=SafetyConfig(level="moderate", sandbox="subprocess"))
    def my_fn(...): ...

When active, each call to the repaired function spawns a fresh Python
subprocess (`sys.executable -I`), pickles args in on stdin, pickles the
return value out on stdout. The child process has no inherited globals
from the caller, so proposals must be self-contained (include their
own imports at the top of the function source).

Limitations:
- Args, kwargs, and return value must be pickle-serializable.
- Each call pays subprocess startup overhead (tens of ms).
- The proposed source must define the function at module scope.
"""

from __future__ import annotations

import pickle
import subprocess
import sys
import textwrap
from collections.abc import Callable
from typing import Any

__all__ = ["SandboxError", "SubprocessSandbox", "make_sandboxed_callable"]


class SandboxError(RuntimeError):
    """Raised when the sandbox itself cannot run the proposal.

    Distinct from exceptions raised *inside* the sandboxed function,
    which are re-raised to the caller as their original type.
    """


_WORKER_SOURCE = textwrap.dedent(
    """
    import pickle, sys, traceback

    def _emit(payload):
        sys.stdout.buffer.write(pickle.dumps(payload))
        sys.stdout.buffer.flush()

    try:
        data = pickle.loads(sys.stdin.buffer.read())
    except Exception as exc:
        _emit({"ok": False, "sandbox_error": f"bad input: {exc}"})
        sys.exit(0)

    try:
        ns = {"__name__": "__sandbox__"}
        exec(data["source"], ns)
        fn = ns.get(data["name"])
        if not callable(fn):
            _emit({"ok": False, "sandbox_error":
                   f"proposed symbol '{data['name']}' is not callable"})
            sys.exit(0)
        value = fn(*data["args"], **data["kwargs"])
    except BaseException as exc:
        try:
            _emit({"ok": False, "exception": exc})
        except Exception:
            _emit({"ok": False, "sandbox_error":
                   f"{type(exc).__name__}: {exc}\\n{traceback.format_exc()}"})
        sys.exit(0)

    try:
        _emit({"ok": True, "value": value})
    except Exception as exc:
        _emit({"ok": False, "sandbox_error":
               f"return value not pickleable: {exc}"})
    """
).strip()


class SubprocessSandbox:
    """Runs proposed code in an isolated Python subprocess.

    Uses `python -I` (isolated mode): ignores PYTHON* env vars, the user
    site-packages directory, and doesn't prepend cwd to sys.path.
    """

    def __init__(self, timeout: float = 30.0, python: str | None = None):
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        self.timeout = timeout
        self.python = python or sys.executable

    def run(
        self, source: str, name: str, args: tuple, kwargs: dict
    ) -> Any:
        try:
            payload = pickle.dumps(
                {"source": source, "name": name, "args": args, "kwargs": kwargs}
            )
        except Exception as err:
            raise SandboxError(f"args not pickleable: {err}") from err

        try:
            proc = subprocess.run(
                [self.python, "-I", "-c", _WORKER_SOURCE],
                input=payload,
                capture_output=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as err:
            raise SandboxError(
                f"sandbox timed out after {self.timeout}s"
            ) from err
        except FileNotFoundError as err:
            raise SandboxError(f"python not found: {self.python}") from err

        if proc.returncode != 0 and not proc.stdout:
            stderr = proc.stderr.decode("utf-8", errors="replace").strip()
            raise SandboxError(
                f"sandbox exited {proc.returncode}: {stderr or '<no stderr>'}"
            )

        if not proc.stdout:
            raise SandboxError("sandbox produced no output")

        try:
            result = pickle.loads(proc.stdout)
        except Exception as err:
            raise SandboxError(f"sandbox output not readable: {err}") from err

        if result.get("ok"):
            return result["value"]
        if "sandbox_error" in result:
            raise SandboxError(result["sandbox_error"])
        if "exception" in result:
            raise result["exception"]
        raise SandboxError(f"unexpected sandbox result: {result!r}")


def make_sandboxed_callable(
    source: str, name: str, sandbox: SubprocessSandbox
) -> Callable:
    """Return a callable that routes each call through `sandbox`.

    The callable quacks like the underlying function: args and kwargs
    pass through, return value comes back, exceptions re-raise.
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return sandbox.run(source, name, args, kwargs)

    wrapper.__name__ = name
    wrapper.__qualname__ = name
    wrapper.__wrapped_source__ = source  # type: ignore[attr-defined]
    return wrapper
