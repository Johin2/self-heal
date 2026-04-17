"""self-heal demo: a naive price parser that heals itself."""

import logging
import sys

from self_heal import repair
from self_heal.llm import GeminiProposer


def test_dollars(fn):
    assert fn("$12.99") == 12.99


def test_dollars_comma(fn):
    assert fn("$1,299.00") == 1299.0


def test_rupees(fn):
    assert fn("₹1,299") == 1299.0


@repair(
    tests=[test_dollars, test_dollars_comma, test_rupees],
    proposer=GeminiProposer(model="gemini-2.5-flash"),
    verbose=True,
    max_attempts=3,
)
def extract_price(text: str) -> float:
    # Naive: only handles "$X.YY" -- fails on commas and other currencies.
    return float(text.replace("$", ""))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    value = extract_price("₹1,299")

    print()
    print(f"  ₹1,299  ->  {value}")
    print(f"  (healed in {extract_price.last_repair.total_attempts} attempts)")
