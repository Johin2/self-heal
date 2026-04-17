"""Minimal self-heal example.

Requires ANTHROPIC_API_KEY in the environment.

Run:
    python examples/basic.py
"""

from __future__ import annotations

import logging

from self_heal import repair

logging.basicConfig(level=logging.INFO, format="%(message)s")


@repair(max_attempts=3, verbose=True)
def divide(a: float, b: float) -> float:
    # Naive: crashes on b == 0.
    return a / b


if __name__ == "__main__":
    print("divide(10, 2) =", divide(10, 2))
    print()
    print("divide(10, 0) =", divide(10, 0))
    print()
    print("Attempts:", divide.last_repair.total_attempts)
