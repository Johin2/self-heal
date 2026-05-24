"""Seed a sample run for an existing user. Useful for populating a
freshly-onboarded account's dashboard with realistic data.

Usage:
    python -m scripts.seed_run_for <user_email>
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import ApiKey, Project, RepairEvent, RepairRun, User
from app.security import generate_api_key


async def main(email: str) -> int:
    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is None:
            print(f"no user with email={email}", file=sys.stderr)
            return 1
        project = (
            await session.execute(select(Project).where(Project.owner_user_id == user.id))
        ).scalar_one_or_none()
        if project is None:
            print("user has no project — they need to sign in once first", file=sys.stderr)
            return 1

        plaintext, prefix, key_hash = generate_api_key()
        session.add(ApiKey(project_id=project.id, name="seed key", prefix=prefix, key_hash=key_hash))

        now = datetime.now(timezone.utc)
        run_key = f"demo-{uuid.uuid4().hex[:8]}"
        run = RepairRun(
            project_id=project.id,
            run_key=run_key,
            function_name="billing.compute_total",
            module_name="myapp.billing",
            status="succeeded",
            started_at=now - timedelta(seconds=5),
            ended_at=now,
            attempts=2,
            final_source="def compute_total(items): return sum(i.price for i in items)",
        )
        session.add(run)
        await session.flush()

        events = [
            ("attempt_start", 1, {}),
            ("attempt_failed", 1, {"error": "TypeError: '>' not supported"}),
            ("propose_start", 2, {}),
            (
                "propose_complete",
                2,
                {"proposed_source": "def compute_total(items): return sum(i.price for i in items)"},
            ),
            ("verify_success", 2, {}),
            ("repair_succeeded", 2, {}),
        ]
        for i, (etype, attempt, payload) in enumerate(events):
            session.add(
                RepairEvent(
                    run_id=run.id,
                    event_id=uuid.uuid4().hex,
                    ts=run.started_at + timedelta(seconds=i),
                    type=etype,
                    attempt_number=attempt,
                    payload=payload,
                )
            )

        await session.commit()
        print(f"seeded run    = {run.id}")
        print(f"project_id    = {project.id}")
        print(f"api_key       = {plaintext}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "")))
