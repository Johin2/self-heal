"""Audit log endpoints: list runs + run detail (with event timeline)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Project, RepairEvent, RepairRun
from app.projects import current_project
from app.schemas import EventRecord, RunDetail, RunSummary

router = APIRouter(prefix="/v1", tags=["runs"])


class RunsPage(BaseModel):
    runs: list[RunSummary]
    next_cursor: str | None = None


@router.get("/runs", response_model=RunsPage)
async def list_runs(
    project: Project = Depends(current_project),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None, description="started_at ISO timestamp from the previous page"),
    status_filter: str | None = Query(None, alias="status"),
    function: str | None = Query(None),
) -> RunsPage:
    stmt = select(RepairRun).where(RepairRun.project_id == project.id)
    if status_filter:
        stmt = stmt.where(RepairRun.status == status_filter)
    if function:
        stmt = stmt.where(RepairRun.function_name == function)
    if cursor:
        from datetime import datetime

        try:
            cursor_dt = datetime.fromisoformat(cursor)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid cursor") from e
        stmt = stmt.where(RepairRun.started_at < cursor_dt)

    stmt = stmt.order_by(desc(RepairRun.started_at)).limit(limit + 1)
    rows = (await session.execute(stmt)).scalars().all()

    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = items[-1].started_at.isoformat() if has_more and items else None

    return RunsPage(
        runs=[RunSummary.model_validate(r) for r in items],
        next_cursor=next_cursor,
    )


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(
    run_id: uuid.UUID,
    project: Project = Depends(current_project),
    session: AsyncSession = Depends(get_session),
) -> RunDetail:
    stmt = select(RepairRun).where(RepairRun.id == run_id, RepairRun.project_id == project.id)
    run = (await session.execute(stmt)).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    events_stmt = (
        select(RepairEvent).where(RepairEvent.run_id == run.id).order_by(RepairEvent.ts)
    )
    events = (await session.execute(events_stmt)).scalars().all()

    return RunDetail(
        id=run.id,
        function_name=run.function_name,
        module_name=run.module_name,
        status=run.status,  # type: ignore[arg-type]
        started_at=run.started_at,
        ended_at=run.ended_at,
        attempts=run.attempts,
        final_error=run.final_error,
        final_source=run.final_source,
        events=[EventRecord.model_validate(e) for e in events],
    )
