"""Retention jobs for user-generated operational records."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence import AuditLog, BIQueryHistory, ModelUsage


async def apply_retention(db: AsyncSession, days: int, now: datetime | None = None) -> dict[str, int]:
    if days < 30:
        raise ValueError("retention must be at least 30 days")
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    deleted = {}
    for name, model in (("bi_queries", BIQueryHistory), ("model_usage", ModelUsage), ("audit_logs", AuditLog)):
        result = await db.execute(delete(model).where(model.created_at < cutoff))
        deleted[name] = int(result.rowcount or 0)
    return deleted
