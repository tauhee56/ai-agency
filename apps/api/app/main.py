import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.db import Base, engine
from app.middleware_security import RateLimitMiddleware
from app.routers import activity, admin, auth, ceo, companies, health, models, ops, org, work
from app.services.result_listener import result_listener_loop

# Import models so metadata is registered
from app import models as _models  # noqa: F401

_stop = asyncio.Event()
_listener_task: asyncio.Task | None = None


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
    version="0.6.0-phase6",
    description="Phases 1–6: foundation through production hardening (partial).",
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware, limit=120, window=60)
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
app.include_router(work.router)
app.include_router(ops.router)
app.include_router(admin.router)
app.include_router(activity.router)


@app.get("/")
def root() -> dict:
    return {
        "name": "ai-company-os",
        "phase": 6,
        "docs": "/docs",
        "metagpt": "disabled" if not settings.metagpt_enabled else "enabled",
        "openhands": "stub" if settings.openhands_enabled else "disabled",
        "hardening": "partial",
    }
