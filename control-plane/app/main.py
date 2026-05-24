from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.routes import auth, ingest, metrics, policy, runs

settings = get_settings()

app = FastAPI(title="self-heal control plane", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(auth.router)
app.include_router(runs.router)
app.include_router(metrics.router)
app.include_router(policy.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
async def health_db() -> dict[str, str]:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        result.scalar_one()
    return {"status": "ok"}
