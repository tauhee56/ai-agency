from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.db import Base, engine
from app.routers import activity, auth, ceo, companies, health, models

# Import models so metadata is registered
from app import models as _models  # noqa: F401


def init_db() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    Base.metadata.create_all(bind=engine)
    # Partial unique index: one default model per company
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
    init_db()
    yield


settings = get_settings()
app = FastAPI(
    title="Autonomous AI Company OS API",
    version="0.1.0-phase1",
    description="Phase 1 foundation: auth, tenancy, model registry, AI CEO stub.",
    lifespan=lifespan,
)

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
app.include_router(activity.router)


@app.get("/")
def root() -> dict:
    return {"name": "ai-company-os", "phase": 1, "docs": "/docs"}
