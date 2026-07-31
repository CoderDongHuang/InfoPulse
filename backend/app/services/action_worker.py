"""Lightweight SLA/dead-letter sweep; external execution remains connector-owned."""
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.database import _get_sessionmaker
from app.models.action_loop import ResponseAction, ActionRun, ActionAudit
async def action_operations_loop(stop):
    while not stop.is_set():
        try:
            async with _get_sessionmaker()() as db:
                now=datetime.now(timezone.utc); rows=(await db.scalars(select(ResponseAction).where(ResponseAction.due_at<now,ResponseAction.status.in_(["draft","approved","executing"])))).all()
                for a in rows: db.add(ActionAudit(organization_id=a.organization_id,action_id=a.id,action="sla.overdue",details={"due_at":a.due_at.isoformat()})); a.status="blocked"
                await db.commit()
        except Exception: pass
        try: await asyncio.wait_for(stop.wait(),30)
        except asyncio.TimeoutError: pass
