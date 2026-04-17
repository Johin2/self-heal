"""Prompt construction and code extraction."""

from __future__ import annotations

import re

from self_heal.types import Failure

REPAIR_SYSTEM = (
    "You are a Python code repair expert. Given a function and its failure, "
    "propose a repaired version of the function that fixes the failure while "
    "preserving the original intent and API (same name, same signature). "
    "Return ONLY valid Python code: one complete function definition. "
    "If you use markdown, wrap in a single ```python block. "
    "Do not include usage examples, explanations, or multiple function definitions."
)


REPAIR_USER_TEMPLATE = """FAILING FUNCTION:
```python
{source}
```

INPUTS THAT CAUSED THE FAILURE:
{inputs}

FAILURE:
- Kind:       {kind}
- Error type: {error_type}
- Message:    {message}

TRACEBACK:
{traceback}

Propose a repaired version of the function. Keep the same name and signature. \
Handle the observed failure and any nearby edge cases you can reasonably infer."""


_CODE_BLOCK = re.compile(r"```(?:python)?\n?(.*?)```", re.DOTALL)


def build_messages(source: str, failure: Failure) -> tuple[str, str]:
    """Build (system, user) prompt pair for a repair request."""
    user = REPAIR_USER_TEMPLATE.format(
        source=source,
        inputs=_format_inputs(failure.inputs),
        kind=failure.kind,
        error_type=failure.error_type,
        message=failure.message,
        traceback=failure.traceback or "(unavailable)",
    )
    return REPAIR_SYSTEM, user


def extract_code(text: str) -> str:
    """Pull Python source out of a markdown-wrapped response, or return as-is."""
    match = _CODE_BLOCK.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _format_inputs(inputs: dict) -> str:
    if not inputs:
        return "(none)"
    lines = [f"  {k} = {v!r}" for k, v in inputs.items()]
    return "\n".join(lines)
