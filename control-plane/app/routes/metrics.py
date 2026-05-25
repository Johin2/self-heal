"""GET /v1/metrics — aggregated reliability stats over a time window."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Project, RepairRun
from app.projects import current_project

router = APIRouter(prefix="/v1", tags=["metrics"])


_RANGE_MAP = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
}


class StatusBreakdown(BaseModel):
    succeeded: int = 0
    exhausted: int = 0
    in_progress: int = 0


class DailyBucket(BaseModel):
    day: str
    succeeded: int
    exhausted: int


class TopFailingFn(BaseModel):
    function_name: str
    count: int


class MetricsResponse(BaseModel):
    range: str
    total_runs: int
    success_rate: float | None
    by_status: StatusBreakdown
    avg_attempts: float | None
    p50_duration_ms: float | None
    p95_duration_ms: float | None
    runs_over_time: list[DailyBucket]
    top_failing_functions: list[TopFailingFn]


@router.get("/metrics", response_model=MetricsResponse)
async def metrics(
    range: str = Query("7d", description="One of: 24h, 7d, 30d, 90d"),
    project: Project = Depends(current_project),
    session: AsyncSession = Depends(get_session),
) -> MetricsResponse:
    delta = _RANGE_MAP.get(range, _RANGE_MAP["7d"])
    since = datetime.now(UTC) - delta

    base = (RepairRun.project_id == project.id, RepairRun.started_at >= since)

    # Headline counts.
    counts_stmt = select(
        func.count().label("total"),
        func.count().filter(RepairRun.status == "succeeded").label("succeeded"),
        func.count().filter(RepairRun.status == "exhausted").label("exhausted"),
        func.count().filter(RepairRun.status == "in_progress").label("in_progress"),
        func.avg(RepairRun.attempts).label("avg_attempts"),
    ).where(*base)
    counts = (await session.execute(counts_stmt)).one()
    total = counts.total or 0
    success_rate = (counts.succeeded / total) if total else None

    # Duration percentiles (only for completed runs).
    duration_secs = func.extract("epoch", RepairRun.ended_at - RepairRun.started_at)
    dur_stmt = select(
        func.percentile_cont(0.5).within_group(duration_secs).label("p50"),
        func.percentile_cont(0.95).within_group(duration_secs).label("p95"),
    ).where(*base, RepairRun.ended_at.is_not(None))
    durations = (await session.execute(dur_stmt)).one()

    # Daily series.
    day_col = func.date_trunc("day", RepairRun.started_at).label("day")
    series_stmt = (
        select(
            day_col,
            func.count().filter(RepairRun.status == "succeeded").label("succeeded"),
            func.count().filter(RepairRun.status == "exhausted").label("exhausted"),
        )
        .where(*base)
        .group_by(day_col)
        .order_by(day_col)
    )
    series = (await session.execute(series_stmt)).all()

    # Top failing functions over the window.
    fail_stmt = (
        select(RepairRun.function_name, func.count().label("count"))
        .where(*base, RepairRun.status == "exhausted")
        .group_by(RepairRun.function_name)
        .order_by(func.count().desc())
        .limit(5)
    )
    top_fails = (await session.execute(fail_stmt)).all()

    return MetricsResponse(
        range=range,
        total_runs=total,
        success_rate=success_rate,
        by_status=StatusBreakdown(
            succeeded=counts.succeeded or 0,
            exhausted=counts.exhausted or 0,
            in_progress=counts.in_progress or 0,
        ),
        avg_attempts=float(counts.avg_attempts) if counts.avg_attempts is not None else None,
        p50_duration_ms=(float(durations.p50) * 1000.0) if durations.p50 is not None else None,
        p95_duration_ms=(float(durations.p95) * 1000.0) if durations.p95 is not None else None,
        runs_over_time=[
            DailyBucket(day=row.day.date().isoformat(), succeeded=row.succeeded, exhausted=row.exhausted)
            for row in series
        ],
        top_failing_functions=[
            TopFailingFn(function_name=row.function_name, count=row.count) for row in top_fails
        ],
    )


# Silence the unused import warning if no callers reference `case` directly.
_ = case
