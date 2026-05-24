"""Auth helpers: API key hashing + FastAPI dependency."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ApiKey, Project

API_KEY_PREFIX = "shc_live_"


def generate_api_key() -> tuple[str, str, str]:
    """Return (plaintext, prefix_display, sha256_hash).

    Plaintext is shown to the user once at creation time; we store only
    the hash and a short prefix for identification in the UI.
    """
    raw = secrets.token_urlsafe(32)
    plaintext = f"{API_KEY_PREFIX}{raw}"
    prefix_display = plaintext[: len(API_KEY_PREFIX) + 8]
    return plaintext, prefix_display, hash_api_key(plaintext)


def hash_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expected `Authorization: Bearer <api-key>`",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token.strip()


async def authenticate_api_key(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> tuple[ApiKey, Project]:
    """Resolve the bearer token to (ApiKey, Project), or raise 401."""
    token = _extract_bearer(authorization)
    token_hash = hash_api_key(token)

    stmt = (
        select(ApiKey, Project)
        .join(Project, Project.id == ApiKey.project_id)
        .where(ApiKey.key_hash == token_hash, ApiKey.revoked_at.is_(None))
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )

    api_key, project = row
    await session.execute(
        update(ApiKey)
        .where(ApiKey.id == api_key.id)
        .values(last_used_at=datetime.now(timezone.utc))
    )
    await session.commit()
    return api_key, project


def new_session_token() -> tuple[str, str]:
    """Return (plaintext, sha256_hash) for a new browser session cookie."""
    raw = secrets.token_urlsafe(48)
    return raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_magic_link_token() -> tuple[str, str]:
    """Return (plaintext, sha256_hash) for a magic-link email token."""
    raw = secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()
