"""Helpers for project scoping under a signed-in user.

For the v0 cut every user has exactly one auto-provisioned default
project. Once we ship a project switcher we'll let the dashboard pass
an explicit project_id.
"""

from __future__ import annotations

import re
import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db import get_session
from app.models import Project, User


def _slug_from_email(email: str) -> str:
    local = email.split("@", 1)[0]
    base = re.sub(r"[^a-z0-9-]+", "-", local.lower()).strip("-") or "user"
    return f"{base}-{uuid.uuid4().hex[:6]}"


async def ensure_default_project(session: AsyncSession, user: User) -> Project:
    """Return the user's first project, creating one if they have none."""
    stmt = select(Project).where(Project.owner_user_id == user.id).order_by(Project.created_at).limit(1)
    project = (await session.execute(stmt)).scalar_one_or_none()
    if project is not None:
        return project

    project = Project(
        owner_user_id=user.id,
        name="Default",
        slug=_slug_from_email(user.email),
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def current_project(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Project:
    project = await ensure_default_project(session, user)
    if project is None:  # pragma: no cover — defensive
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No project")
    return project
