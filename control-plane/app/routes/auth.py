"""Magic-link sign-in.

Flow:
  1. POST /v1/auth/request-link {"email": "..."} — issues a single-use
     token, sends an email with /auth/verify?token=... .
  2. POST /v1/auth/verify {"token": "..."} — consumes the token,
     creates (or returns) the user, opens a session and sets the
     `cp_session` HttpOnly cookie.
  3. POST /v1/auth/logout — revokes the current session.
  4. GET  /v1/auth/me — returns the current user (uses cookie).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import SESSION_COOKIE, current_user
from app.config import get_settings
from app.db import get_session
from app.email import send_magic_link
from app.models import MagicLinkToken, User
from app.models import Session as SessionRow
from app.schemas import MagicLinkRequest, MagicLinkResponse
from app.security import new_magic_link_token, new_session_token

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class VerifyRequest(BaseModel):
    token: str


class MeResponse(BaseModel):
    id: str
    email: str


def _is_secure_cookie() -> bool:
    base = get_settings().dashboard_base_url
    return base.startswith("https://")


def _set_session_cookie(response: Response, token: str, expires_at: datetime) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=_is_secure_cookie(),
        samesite="lax",
        expires=expires_at,
        path="/",
    )


@router.post("/request-link", response_model=MagicLinkResponse)
async def request_link(
    body: MagicLinkRequest,
    session: AsyncSession = Depends(get_session),
) -> MagicLinkResponse:
    settings = get_settings()
    plaintext, token_hash = new_magic_link_token()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.magic_link_ttl_minutes)

    session.add(
        MagicLinkToken(
            token_hash=token_hash,
            email=body.email.lower(),
            expires_at=expires_at,
        )
    )
    await session.commit()

    link = f"{settings.dashboard_base_url.rstrip('/')}/auth/verify?token={plaintext}"
    await send_magic_link(to=body.email, link=link)

    # Always return success — never leak which emails are on the waitlist.
    return MagicLinkResponse(sent=True)


@router.post("/verify")
async def verify(
    body: VerifyRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    import hashlib

    token_hash = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)

    row = (
        await session.execute(
            select(MagicLinkToken).where(MagicLinkToken.token_hash == token_hash)
        )
    ).scalar_one_or_none()
    if row is None or row.consumed_at is not None or row.expires_at < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired link")

    row.consumed_at = now

    user = (
        await session.execute(select(User).where(User.email == row.email))
    ).scalar_one_or_none()
    if user is None:
        user = User(email=row.email)
        session.add(user)
        await session.flush()

    plaintext, session_hash = new_session_token()
    settings = get_settings()
    expires_at = now + timedelta(days=settings.session_ttl_days)
    session.add(
        SessionRow(
            user_id=user.id,
            token_hash=session_hash,
            expires_at=expires_at,
            user_agent=request.headers.get("user-agent"),
            ip=(request.client.host if request.client else None),
        )
    )
    await session.commit()

    _set_session_cookie(response, plaintext, expires_at)
    return MeResponse(id=str(user.id), email=user.email)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    # Revoke all sessions for this user from this device class — simpler
    # to wipe everything than to thread the request cookie down here.
    from sqlalchemy import update

    await session.execute(
        update(SessionRow)
        .where(SessionRow.user_id == user.id, SessionRow.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return Response(status_code=204)


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(current_user)) -> MeResponse:
    return MeResponse(id=str(user.id), email=user.email)
