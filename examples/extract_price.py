"""A realistic self-heal example: messy real-world input.

Requires ANTHROPIC_API_KEY in the environment.

Run:
    python examples/extract_price.py
"""

from __future__ import annotations

import logging

from self_heal import repair

logging.basicConfig(level=logging.INFO, format="%(message)s")


@repair(max_attempts=3, verbose=True)
def extract_price(text: str) -> float:
    # Naive: only handles "$X.YY" with no commas.
    return float(text.replace("$", ""))


if __name__ == "__main__":
    samples = ["$12.99", "₹1,299", "€5,49", "1000.50 USD", "  $4,999.00 "]
    for sample in samples:
        try:
            value = extract_price(sample)
            print(f"{sample!r:>18}  ->  {value}")
        except Exception as e:
            print(f"{sample!r:>18}  ->  FAILED: {e}")
