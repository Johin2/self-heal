"""Verified repair: reject results that fail a user-provided predicate.

Without `verify`, a function that returns the wrong type or out-of-range value
silently succeeds. `verify` turns any predicate into a repair trigger.

Requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

from self_heal import repair


@repair(
    max_attempts=3,
    verify=lambda v: isinstance(v, float) and 0 < v < 1_000_000,
    verbose=True,
)
def extract_price(text: str) -> float:
    # Naive: will return 0.0 for empty string, or negative for "$-5".
    return float(text.replace("$", ""))


if __name__ == "__main__":
    for sample in ["$12.99", "$-5", "", "₹1,299"]:
        try:
            value = extract_price(sample)
            print(f"{sample!r:>12}  ->  {value}")
        except Exception as exc:
            print(f"{sample!r:>12}  ->  FAILED: {exc}")
