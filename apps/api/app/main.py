import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.db import Base, engine
from app.middleware_security import RateLimitMiddleware
from app.routers import (
    activity,
    admin,
    auth,
    ceo,
    companies,
    health,
    models,
    ops,
    org,
    schedules,
    soul,
    webhooks,
    work,
)
from app.services.result_listener import result_listener_loop

# Import models so metadata is registered
from app import models as _models  # noqa: F401

_stop = asyncio.Event()
_listener_task: asyncio.Task | None = None


def _soft_migrate(conn) -> None:
    stmts = [
        "ALTER TABLE task_runs ADD COLUMN IF NOT EXISTS dispatch_id uuid",
        "ALTER TABLE task_runs ADD COLUMN IF NOT EXISTS heartbeat_at timestamptz",
        "ALTER TABLE task_runs ADD COLUMN IF NOT EXISTS outcome text",
        "ALTER TABLE task_runs ADD COLUMN IF NOT EXISTS terminal_received boolean NOT NULL DEFAULT false",
        "ALTER TABLE approvals ADD COLUMN IF NOT EXISTS waiting_on text NOT NULL DEFAULT 'founder'",
        "ALTER TABLE approvals ADD COLUMN IF NOT EXISTS suggested_actions jsonb NOT NULL DEFAULT '[]'::jsonb",
    ]
    for s in stmts:
        conn.execute(text(s))


def init_db() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_model_configs_company_default
                ON model_configs (company_id)
                WHERE is_default = true
                """
            )
        )
        _soft_migrate(conn)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _listener_task
    init_db()
    _stop.clear()
    _listener_task = asyncio.create_task(result_listener_loop(_stop))
    yield
    _stop.set()
    if _listener_task:
        await asyncio.wait([_listener_task], timeout=2)


settings = get_settings()
app = FastAPI(
    title="Autonomous AI Company OS API",
    version="0.6.1-orca",
    description="Orca must-have concept adoptions on Phases 1–6 foundation.",
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware, limit=300, window=60)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(models.router)
app.include_router(ceo.router)
app.include_router(org.router)
app.include_router(soul.router)
app.include_router(work.router)
app.include_router(ops.router)
app.include_router(schedules.router)
app.include_router(webhooks.router)
app.include_router(admin.router)
app.include_router(activity.router)


@app.get("/")
def root() -> dict:
    return {
        "name": "ai-company-os",
        "phase": 6,
        "adapter_protocol": "1.1",
        "docs": "/docs",
        "metagpt": "disabled" if not settings.metagpt_enabled else "enabled",
        "openhands": "stub" if settings.openhands_enabled else "disabled",
        "hardening": "partial",
        "orca_adoptions": ["M1", "M2", "M3", "M4", "M5", "M6"],
    }
