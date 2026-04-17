"""Self-heal works transparently on async functions.

The decorator detects `async def` and awaits the coroutine; the proposer
call is run in a thread pool executor so your event loop stays free.

Requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import asyncio

from self_heal import repair


@repair(max_attempts=3, verbose=True)
async def fetch_and_parse(text: str) -> float:
    # Pretend this is an async tool call. Naive parser fails on commas.
    await asyncio.sleep(0)
    return float(text.replace("$", ""))


async def main():
    for sample in ["$12.99", "$1,299", "₹4,999"]:
        value = await fetch_and_parse(sample)
        print(f"{sample!r:>10}  ->  {value}")


if __name__ == "__main__":
    asyncio.run(main())
