"""Smoke-test every example under examples/.

Ensures that examples parse and import cleanly after refactors.

Rules
-----
ImportError naming a known optional SDK  -> pytest.skip (expected in bare envs)
SDK raising on missing credentials       -> pytest.skip (optional, not configured)
Any other exception                      -> fail (real bug)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_OPTIONAL_PACKAGES = {
    "anthropic", "openai", "google", "cohere",
    "mistralai", "crewai", "langchain", "agents",
    "claude_agent_sdk",
}

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
EXAMPLE_FILES = sorted(EXAMPLES_DIR.rglob("*.py"))


def _is_optional_import_error(exc: ImportError) -> bool:
    msg = str(exc).lower()
    return any(pkg in msg for pkg in _OPTIONAL_PACKAGES)


def _is_credential_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "api key" in msg or "api_key" in msg or "credential" in msg


@pytest.mark.parametrize("example_path", EXAMPLE_FILES, ids=lambda p: p.name)
def test_example_imports(example_path: Path) -> None:
    if str(EXAMPLES_DIR) not in sys.path:
        sys.path.insert(0, str(EXAMPLES_DIR))

    spec = importlib.util.spec_from_file_location(example_path.stem, example_path)
    assert spec and spec.loader, f"Could not create spec for {example_path.name}"

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except ImportError as exc:
        if _is_optional_import_error(exc):
            pytest.skip(f"Optional dependency not installed -- {exc}")
        raise
    except Exception as exc:
        if _is_credential_error(exc):
            pytest.skip(f"Optional SDK not configured -- {exc}")
        raise
