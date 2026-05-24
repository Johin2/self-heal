"""Session auth: the current-user dependency.

A signed-in browser holds a cookie named `cp_session` whose value is
the plaintext session token. We hash it (sha256) and look up the
sessions table for an active row tied to a user.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Session as SessionRow
from app.models import User

SESSION_COOKIE = "cp_session"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def current_user(
    cp_session: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not cp_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in")

    token_hash = _hash(cp_session)
    now = datetime.now(timezone.utc)
    stmt = (
        select(SessionRow, User)
        .join(User, User.id == SessionRow.user_id)
        .where(
            SessionRow.token_hash == token_hash,
            SessionRow.expires_at > now,
            SessionRow.revoked_at.is_(None),
        )
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid or expired")

    session_row, user = row
    session_row.last_used_at = now
    await session.commit()
    return user
