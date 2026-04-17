"""Test-driven repair: self-heal until all your tests pass.

Each test takes the function being repaired and raises on failure.
The repair loop runs until every test passes for the given call.

Requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

from self_heal import repair


def test_parses_dollars(fn):
    assert fn("$12.99") == 12.99


def test_parses_rupees(fn):
    assert fn("₹1,299") == 1299.0


def test_parses_euros_with_comma_decimal(fn):
    assert fn("€5,49") == 5.49


def test_handles_surrounding_whitespace(fn):
    assert fn("  $4,999.00  ") == 4999.0


@repair(
    max_attempts=5,
    tests=[
        test_parses_dollars,
        test_parses_rupees,
        test_parses_euros_with_comma_decimal,
        test_handles_surrounding_whitespace,
    ],
    verbose=True,
)
def extract_price(text: str) -> float:
    # Naive: only handles "$X.YY" with no commas.
    return float(text.replace("$", ""))


if __name__ == "__main__":
    # Calling with any input triggers the repair loop: self-heal won't
    # accept the function as "working" until every test above passes.
    print(extract_price("$12.99"))
    print("Repaired in", extract_price.last_repair.total_attempts, "attempt(s).")
