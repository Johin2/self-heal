"""Stream LLM tokens as the proposer generates the repair.

Pass `on_event=...` to observe each `propose_chunk` event. Deltas arrive
as they come off the wire, so you can build a progress UI, a CLI typing
animation, or a live diff renderer.

Works out of the box with `ClaudeProposer`, `OpenAIProposer`,
`GeminiProposer`, and `LiteLLMProposer`. Any custom proposer that
exposes `propose_stream(system, user) -> Iterator[str]` will also be
streamed; others are called via the plain `propose()` path.
"""

from __future__ import annotations

import sys

from self_heal import RepairEvent, repair


def on_event(event: RepairEvent) -> None:
    if event.type == "propose_start":
        print("\n[self-heal] proposing repair: ", end="", flush=True)
    elif event.type == "propose_chunk" and event.delta:
        sys.stdout.write(event.delta)
        sys.stdout.flush()
    elif event.type == "propose_complete":
        print()  # newline after the stream


def test_comma(fn):
    assert fn("$1,299") == 1299.0


def test_rupee(fn):
    assert fn("Rs 500") == 500.0


@repair(tests=[test_comma, test_rupee], on_event=on_event)
def extract_price(text: str) -> float:
    return float(text.replace("$", ""))  # naive


if __name__ == "__main__":
    print(extract_price("$1,299"))
