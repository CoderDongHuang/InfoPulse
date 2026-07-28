import hmac
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from app.config import get_settings
from app.core.database import _get_engine
from app.core.observability import metrics
from app.core import redis as redis_core

router = APIRouter(prefix="/api/v1", tags=["Operations"])


@router.get("/health/live")
async def live():
    return {"status": "ok", "version": get_settings().APP_VERSION}


@router.get("/health/ready")
async def ready():
    checks = {"database": False, "redis": False}
    try:
        async with _get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass
    try:
        checks["redis"] = bool(redis_core.redis_client and await redis_core.redis_client.ping())
    except Exception:
        pass
    if not checks["database"]:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})
    return {"status": "ready" if checks["redis"] else "degraded", "checks": checks}


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def prometheus_metrics(x_metrics_token: str = Header(default="")):
    expected = get_settings().METRICS_TOKEN
    if expected and not hmac.compare_digest(x_metrics_token, expected):
        raise HTTPException(status_code=403, detail="Invalid metrics token")
    return metrics.render()
