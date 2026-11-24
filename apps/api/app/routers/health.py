from fastapi import APIRouter

from app.config import get_settings
from app.db import check_db
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    redis_ok = False
    try:
        import redis

        client = redis.from_url(get_settings().redis_url, socket_connect_timeout=1)
        redis_ok = client.ping() is True
    except Exception:
        redis_ok = False

    db_ok = check_db()
    status = "ok" if db_ok else "degraded"
    return HealthResponse(status=status, db=db_ok, redis=redis_ok)
