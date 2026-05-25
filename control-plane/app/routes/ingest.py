"""POST /v1/events — accept batches of RepairEvent from the OSS client."""

from __future__ import annotations

import uuid
from datetime import UTC

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ApiKey, Project, RepairEvent, RepairRun
from app.schemas import IngestBatch, IngestEvent, IngestResponse
from app.security import authenticate_api_key

router = APIRouter(prefix="/v1", tags=["ingest"])


_TERMINAL_TYPES = {"repair_succeeded", "repair_exhausted"}


async def _open_or_get_run(
    session: AsyncSession, project_id: uuid.UUID, event: IngestEvent
) -> RepairRun:
    stmt = select(RepairRun).where(
        RepairRun.project_id == project_id, RepairRun.run_key == event.run_key
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing

    run = RepairRun(
        project_id=project_id,
        run_key=event.run_key,
        function_name=event.function_name,
        module_name=event.module_name,
        status="in_progress",
        started_at=event.ts,
        attempts=0,
    )
    session.add(run)
    await session.flush()
    return run


def _apply_event_to_run(run: RepairRun, event: IngestEvent) -> None:
    if event.attempt_number is not None:
        run.attempts = max(run.attempts, event.attempt_number)
    if event.type == "repair_succeeded":
        run.status = "succeeded"
        run.ended_at = event.ts
        if isinstance(event.payload, dict):
            run.final_source = event.payload.get("proposed_source")
    elif event.type == "repair_exhausted":
        run.status = "exhausted"
        run.ended_at = event.ts
        if isinstance(event.payload, dict):
            run.final_error = event.payload.get("error")


@router.post("/events", response_model=IngestResponse, status_code=202)
async def post_events(
    batch: IngestBatch,
    auth: tuple[ApiKey, Project] = Depends(authenticate_api_key),
    session: AsyncSession = Depends(get_session),
) -> IngestResponse:
    _, project = auth

    runs_touched: dict[uuid.UUID, RepairRun] = {}
    accepted = 0
    duplicates = 0

    # Group events by run_key so each run is loaded once.
    for event in sorted(batch.events, key=lambda e: e.ts):
        run = await _open_or_get_run(session, project.id, event)

        ts = event.ts if event.ts.tzinfo else event.ts.replace(tzinfo=UTC)

        stmt = (
            pg_insert(RepairEvent)
            .values(
                run_id=run.id,
                event_id=event.event_id,
                ts=ts,
                type=event.type,
                attempt_number=event.attempt_number,
                payload=event.payload,
            )
            .on_conflict_do_nothing(index_elements=["run_id", "event_id"])
            .returning(RepairEvent.id)
        )
        result = await session.execute(stmt)
        inserted_id = result.scalar_one_or_none()
        if inserted_id is None:
            duplicates += 1
            continue

        accepted += 1
        _apply_event_to_run(run, event)
        runs_touched[run.id] = run

        if event.type in _TERMINAL_TYPES and run.ended_at is None:
            run.ended_at = ts

    await session.commit()

    return IngestResponse(
        accepted=accepted,
        duplicates=duplicates,
        runs=list(runs_touched.keys()),
    )
