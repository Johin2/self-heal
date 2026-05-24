"""Pure-logic tests for app.policy_engine.

No DB, no FastAPI — just the rule evaluator's behaviour: priority order,
operators, missing-field handling, default-allow, and the catch-all rule
(empty conditions) semantics.
"""

from __future__ import annotations

from app.policy_engine import evaluate


def _ev(**kw):
    base = {"type": "attempt_failed", "function_name": "fn", "payload": {}}
    base.update(kw)
    return base


def _rule(name, *, conditions=(), action="notify", priority=100, enabled=True, id="00000000-0000-0000-0000-000000000001"):
    return {
        "id": id,
        "name": name,
        "enabled": enabled,
        "priority": priority,
        "conditions": list(conditions),
        "action": action,
    }


def test_default_allow_when_no_rules():
    d = evaluate(_ev(), [])
    assert d.action == "allow"
    assert d.matched_rule_id is None


def test_simple_match_returns_action_and_name():
    rule = _rule("block destructive", conditions=[{"field": "type", "op": "eq", "value": "install_failed"}], action="block")
    d = evaluate(_ev(type="install_failed"), [rule])
    assert d.action == "block"
    assert d.matched_rule_name == "block destructive"


def test_priority_order_first_match_wins():
    catch_all = _rule("catch-all", conditions=[], action="notify", priority=900)
    high_pri_block = _rule(
        "block",
        conditions=[{"field": "type", "op": "eq", "value": "attempt_failed"}],
        action="block",
        priority=10,
    )
    d = evaluate(_ev(type="attempt_failed"), [catch_all, high_pri_block])
    assert d.action == "block"
    assert d.matched_rule_name == "block"


def test_disabled_rules_are_skipped():
    rule = _rule(
        "would block",
        conditions=[{"field": "type", "op": "eq", "value": "attempt_failed"}],
        action="block",
        enabled=False,
    )
    d = evaluate(_ev(type="attempt_failed"), [rule])
    assert d.action == "allow"


def test_contains_and_regex_against_error_message():
    rule_contains = _rule(
        "contains",
        conditions=[{"field": "error_message", "op": "contains", "value": "division"}],
        action="block",
    )
    rule_regex = _rule(
        "regex",
        conditions=[{"field": "error_message", "op": "regex", "value": r"^Zero\w+Error"}],
        action="notify",
        priority=200,
    )
    event = _ev(payload={"failure": {"message": "ZeroDivisionError: division by zero"}})
    d = evaluate(event, [rule_contains, rule_regex])
    assert d.action == "block"  # higher-priority (lower number) wins
    assert d.matched_rule_name == "contains"


def test_gte_on_attempt_number():
    rule = _rule(
        "many attempts",
        conditions=[{"field": "attempt_number", "op": "gte", "value": 3}],
        action="notify",
    )
    assert evaluate(_ev(attempt_number=2), [rule]).action == "allow"
    assert evaluate(_ev(attempt_number=3), [rule]).action == "notify"


def test_missing_field_does_not_match_unless_ne():
    rule = _rule(
        "needs module",
        conditions=[{"field": "module_name", "op": "eq", "value": "billing"}],
        action="block",
    )
    assert evaluate(_ev(), [rule]).action == "allow"

    ne_rule = _rule(
        "must not be foo",
        conditions=[{"field": "module_name", "op": "ne", "value": "foo"}],
        action="notify",
    )
    assert evaluate(_ev(), [ne_rule]).action == "notify"


def test_empty_conditions_is_catch_all():
    rule = _rule("catch", conditions=[], action="notify", priority=999)
    d = evaluate(_ev(), [rule])
    assert d.action == "notify"
    assert d.matched_rule_name == "catch"


def test_all_conditions_must_match_to_fire_rule():
    rule = _rule(
        "two conds",
        conditions=[
            {"field": "type", "op": "eq", "value": "attempt_failed"},
            {"field": "function_name", "op": "eq", "value": "billing.compute_total"},
        ],
        action="block",
    )
    # only one matches -> no fire
    assert evaluate(_ev(type="attempt_failed", function_name="other"), [rule]).action == "allow"
    # both match -> fire
    assert evaluate(_ev(type="attempt_failed", function_name="billing.compute_total"), [rule]).action == "block"
