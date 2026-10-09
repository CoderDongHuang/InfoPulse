"""Advance durable actions and sweep missed SLAs."""
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.database import _get_sessionmaker
from app.models.action_loop import ResponseAction, ActionRun, ActionAudit
from app.services.action_loop import advance_action
from app.services.dispatch import process_dispatch_once
from app.services.platform import process_webhook_once
async def action_operations_loop(stop):
    while not stop.is_set():
        try:
            await process_dispatch_once()
            await process_webhook_once()
            async with _get_sessionmaker()() as db:
                now=datetime.now(timezone.utc); rows=(await db.scalars(select(ResponseAction).where(ResponseAction.due_at<now,ResponseAction.status.in_(["draft","approved","executing"])))).all()
                for a in rows: db.add(ActionAudit(organization_id=a.organization_id,action_id=a.id,action="sla.overdue",details={"due_at":a.due_at.isoformat()})); a.status="blocked"
                runs=(await db.scalars(select(ActionRun).where(ActionRun.status.in_(["queued","waiting_receipt","waiting_dispatch"])).with_for_update(skip_locked=True))).all()
                for run in runs:await advance_action(db,run)
                await db.commit()
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Action worker iteration failed")
        try: await asyncio.wait_for(stop.wait(),30)
        except asyncio.TimeoutError: pass
