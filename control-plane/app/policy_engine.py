"""Policy rule evaluation.

Rules are JSON: a list of {field, op, value} conditions AND-ed together,
plus an action (allow / block / notify). Rules are evaluated by ascending
priority and the first match wins; if no rule matches the default is
allow.

This module is pure (no DB) so it can be unit-tested in isolation. The
routes layer is responsible for loading rules for a project.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class Decision:
    action: str  # "allow" | "block" | "notify"
    matched_rule_id: str | None = None
    matched_rule_name: str | None = None


def _field_value(event: dict[str, Any], field: str) -> Any:
    if field == "type":
        return event.get("type")
    if field == "function_name":
        return event.get("function_name")
    if field == "module_name":
        return event.get("module_name")
    if field == "attempt_number":
        return event.get("attempt_number")
    if field == "error_message":
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            return None
        # Try the most common shapes the OSS client emits.
        failure = payload.get("failure")
        if isinstance(failure, dict) and failure.get("message"):
            return failure["message"]
        return payload.get("error")
    return None


def _match(value: Any, op: str, target: Any) -> bool:
    if value is None:
        # `ne` against a missing field is still True; everything else is False.
        return op == "ne" and target is not None

    if op == "eq":
        return value == target
    if op == "ne":
        return value != target
    if op == "contains":
        return isinstance(value, str) and isinstance(target, str) and target in value
    if op == "regex":
        try:
            return isinstance(value, str) and re.search(str(target), value) is not None
        except re.error:
            return False
    if op == "gte":
        try:
            return float(value) >= float(target)
        except (TypeError, ValueError):
            return False
    if op == "lte":
        try:
            return float(value) <= float(target)
        except (TypeError, ValueError):
            return False
    return False


def evaluate(event: dict[str, Any], rules: list[dict[str, Any]]) -> Decision:
    """Walk rules in priority order; first match wins."""
    ordered = sorted(rules, key=lambda r: (r.get("priority", 100), r.get("name", "")))
    for rule in ordered:
        if not rule.get("enabled", True):
            continue
        conditions = rule.get("conditions") or []
        if not conditions:
            # An empty-condition rule matches everything — useful as a catch-all.
            return Decision(
                action=rule.get("action", "notify"),
                matched_rule_id=rule.get("id"),
                matched_rule_name=rule.get("name"),
            )
        if all(_match(_field_value(event, c["field"]), c["op"], c["value"]) for c in conditions):
            return Decision(
                action=rule.get("action", "notify"),
                matched_rule_id=rule.get("id"),
                matched_rule_name=rule.get("name"),
            )
    return Decision(action="allow")
