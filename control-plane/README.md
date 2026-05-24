# self-heal control plane

Hosted backend for self-heal: audit log, observability, policy engine. FastAPI + Postgres (Neon).

Closed-source — distinct from the OSS library in `../src/self_heal/`.

## Dev

```bash
cd control-plane
python -m venv .venv && . .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

cp .env.example .env.local                     # fill in DATABASE_URL, SECRET_KEY, RESEND_API_KEY
alembic upgrade head                            # apply schema
uvicorn app.main:app --reload --port 8000
```

Smoke checks:

```bash
curl http://localhost:8000/health         # {"status":"ok"}
curl http://localhost:8000/health/db      # {"status":"ok"} — verifies Postgres connection
```

## Deploy

Render: connect this directory, set the env vars from `.env.example`, point the start command at `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. The included `Dockerfile` is the source of truth.
