"""Transactional outbox; uncertain deliveries are never automatically resent."""
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select, update
from app.core.database import _get_sessionmaker
from app.models.dispatch import DispatchJob
from app.models.platform import ConnectorInstallation
from app.schemas.commercialization import ConnectorExecute
from app.services.commercialization import execute_connector


async def enqueue_dispatch(db, *, organization_id, workspace_id, installation_id, message, key, action_id=None):
    existing = await db.scalar(select(DispatchJob).where(DispatchJob.organization_id == organization_id, DispatchJob.idempotency_key == key))
    if existing:
        if existing.installation_id != installation_id or existing.message != message or existing.action_id != action_id or existing.workspace_id != workspace_id:
            raise ValueError("Dispatch idempotency key reused with different input")
        return existing
    install = await db.get(ConnectorInstallation, installation_id)
    if not install or install.organization_id != organization_id or install.workspace_id != workspace_id or install.status != "approved" or install.revoked_at:
        raise ValueError("Approved connector installation in the selected workspace required")
    if not isinstance(message, str) or not 1 <= len(message) <= 12000 or not install.config.get("webhook_url"):
        raise ValueError("Connector requires a configured webhook and a nonempty message")
    row = DispatchJob(organization_id=organization_id, workspace_id=workspace_id, installation_id=installation_id, message=message, idempotency_key=key, action_id=action_id)
    db.add(row)
    await db.flush()
    return row


async def process_dispatch_once(sessions=None, client=None):
    factory = sessions or _get_sessionmaker()
    async with factory() as db:
        at = datetime.now(timezone.utc)
        await db.execute(update(DispatchJob).where(DispatchJob.status == "running", DispatchJob.claimed_at < at - timedelta(minutes=2)).values(status="unknown", error="Worker interrupted; verify remote delivery before retry", finished_at=at))
        identifier = await db.scalar(select(DispatchJob.id).where(DispatchJob.status == "pending").order_by(DispatchJob.created_at).limit(1))
        if not identifier:
            await db.commit()
            return False
        claimed = await db.execute(update(DispatchJob).where(DispatchJob.id == identifier, DispatchJob.status == "pending").values(status="running", claimed_at=at))
        await db.commit()
        if claimed.rowcount != 1:
            return False
        job = await db.get(DispatchJob, identifier)
        try:
            install = await db.get(ConnectorInstallation, job.installation_id)
            if not install or install.workspace_id != job.workspace_id:
                raise ValueError("Connector workspace changed")
            payload = ConnectorExecute(installation_id=job.installation_id, provider=install.connector_key, webhook_url=install.config.get("webhook_url", ""), message=job.message, action_id=job.action_id, idempotency_key=job.idempotency_key)
            execution = await execute_connector(db, job.organization_id, payload, client)
            job.status = execution.status if execution.status in {"succeeded", "failed"} else "unknown"
            job.result = {"execution_id": execution.id, "response_code": execution.response_code, "external_reference": execution.external_reference}
            job.error = execution.error
        except (HTTPException, ValueError) as exc:
            job.status = "failed"
            job.error = str(getattr(exc, "detail", exc))[:1000]
        job.finished_at = datetime.now(timezone.utc)
        await db.commit()
        return True
