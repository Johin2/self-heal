"""Prompt construction and code extraction."""

from __future__ import annotations

import re

from self_heal.types import Failure, RepairAttempt

REPAIR_SYSTEM = (
    "You are a Python code repair expert. Given a function and its failure "
    "(exception, verifier rejection, or failed test), propose a repaired "
    "version of the function that fixes the failure while preserving the "
    "original intent and API (same name, same signature). "
    "Return ONLY valid Python code: one complete function definition. "
    "If you use markdown, wrap in a single ```python block. "
    "Do not include usage examples, multiple function definitions, or "
    "explanations outside the code."
)


_USER_TEMPLATE = """ORIGINAL FUNCTION:
```python
{source}
```

INPUTS THAT CAUSED THIS FAILURE:
{inputs}

CURRENT FAILURE:
- Kind:       {kind}
- Error type: {error_type}
- Message:    {message}

TRACEBACK:
{traceback}
{history_section}{extra_section}
Propose a repaired version of the function. Keep the same name and signature. \
Handle the observed failure and any nearby edge cases you can reasonably infer."""


_HISTORY_TEMPLATE = """
PREVIOUS REPAIR ATTEMPTS — ALL FAILED. Do NOT propose any of these again:
{attempts_block}
"""


_CODE_BLOCK = re.compile(r"```(?:python)?\n?(.*?)```", re.DOTALL)


def build_messages(
    source: str,
    failure: Failure,
    history: list[RepairAttempt] | None = None,
    extra: str | None = None,
) -> tuple[str, str]:
    """Build (system, user) prompt pair for a repair request.

    `history` lets the model see and avoid repeating prior failed fixes.
    `extra` is appended as free-form user instructions.
    """
    history_section = _format_history(history) if history else ""
    extra_section = f"\nADDITIONAL USER INSTRUCTIONS:\n{extra}\n" if extra else ""

    user = _USER_TEMPLATE.format(
        source=source,
        inputs=_format_inputs(failure.inputs),
        kind=failure.kind,
        error_type=failure.error_type,
        message=failure.message,
        traceback=failure.traceback or "(unavailable)",
        history_section=history_section,
        extra_section=extra_section,
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


def _format_history(attempts: list[RepairAttempt]) -> str:
    # Only show attempts that actually proposed a repair; skip the
    # bare failure that triggered the *current* repair request.
    relevant = [a for a in attempts if a.proposed_source is not None]
    if not relevant:
        return ""

    blocks = []
    for a in relevant:
        if a.error_after_repair:
            outcome = f"could not be installed: {a.error_after_repair}"
        else:
            outcome = "did not fix the problem"
        blocks.append(
            f"--- Attempt {a.attempt_number} (FAILED) ---\n"
            f"```python\n{a.proposed_source}\n```\n"
            f"This proposal {outcome}."
        )

    return _HISTORY_TEMPLATE.format(attempts_block="\n\n".join(blocks))
