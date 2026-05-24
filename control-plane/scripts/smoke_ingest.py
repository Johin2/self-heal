"""End-to-end smoke test for the ingestion API.

Spins up the FastAPI app in-process via httpx.ASGITransport, posts a
complete repair sequence, verifies idempotency, and prints results.

Usage:
    SHC_DEMO_API_KEY=... python -m scripts.smoke_ingest
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from app.main import app


def _event(
    run_key: str,
    type_: str,
    *,
    fn: str = "compute_total",
    attempt: int | None = None,
    payload: dict | None = None,
    when: datetime | None = None,
) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "ts": (when or datetime.now(timezone.utc)).isoformat(),
        "run_key": run_key,
        "type": type_,
        "function_name": fn,
        "module_name": "demo.billing",
        "attempt_number": attempt,
        "payload": payload or {},
    }


async def main() -> int:
    api_key = os.environ.get("SHC_DEMO_API_KEY")
    if not api_key:
        print("set SHC_DEMO_API_KEY to a real key from seed_demo.py", file=sys.stderr)
        return 2

    run_key = f"demo-run-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    events = [
        _event(run_key, "attempt_start", attempt=1, when=now),
        _event(
            run_key,
            "attempt_failed",
            attempt=1,
            payload={"error": "ZeroDivisionError: division by zero"},
            when=now + timedelta(seconds=1),
        ),
        _event(run_key, "propose_start", attempt=2, when=now + timedelta(seconds=2)),
        _event(
            run_key,
            "propose_complete",
            attempt=2,
            payload={"proposed_source": "def f(): return 1"},
            when=now + timedelta(seconds=3),
        ),
        _event(
            run_key,
            "repair_succeeded",
            attempt=2,
            payload={"proposed_source": "def f(): return 1"},
            when=now + timedelta(seconds=4),
        ),
    ]

    transport = httpx.ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post("/v1/events", json={"events": events}, headers=headers)
        print("first batch:", r1.status_code, r1.json())

        # Replay to verify idempotency.
        r2 = await client.post("/v1/events", json={"events": events}, headers=headers)
        print("replay:    ", r2.status_code, r2.json())

        # Unknown key -> 401.
        r3 = await client.post(
            "/v1/events",
            json={"events": events},
            headers={"Authorization": "Bearer shc_live_definitely-not-a-real-key"},
        )
        print("bad key:   ", r3.status_code, r3.json())

    return 0 if r1.status_code == 202 and r2.json()["duplicates"] == 5 and r3.status_code == 401 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
