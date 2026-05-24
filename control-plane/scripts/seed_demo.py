"""Seed a demo user, project, and API key. Prints the plaintext API key.

Usage:
    python -m scripts.seed_demo
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models import ApiKey, Project, User
from app.security import generate_api_key

DEMO_EMAIL = "demo@self-heal.dev"
DEMO_PROJECT_SLUG = "demo"


async def main() -> int:
    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == DEMO_EMAIL))
        ).scalar_one_or_none()
        if user is None:
            user = User(email=DEMO_EMAIL)
            session.add(user)
            await session.flush()

        project = (
            await session.execute(
                select(Project).where(Project.slug == DEMO_PROJECT_SLUG)
            )
        ).scalar_one_or_none()
        if project is None:
            project = Project(owner_user_id=user.id, name="Demo", slug=DEMO_PROJECT_SLUG)
            session.add(project)
            await session.flush()

        plaintext, prefix, key_hash = generate_api_key()
        api_key = ApiKey(
            project_id=project.id, name="seed-script key", prefix=prefix, key_hash=key_hash
        )
        session.add(api_key)
        await session.commit()

        print(f"user_id     = {user.id}")
        print(f"project_id  = {project.id}")
        print(f"api_key     = {plaintext}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
