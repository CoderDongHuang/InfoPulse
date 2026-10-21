"""Atomic account removal with post-commit, retryable object cleanup."""
import asyncio
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from app.models.user import User
from app.models.enterprise import Organization, OrganizationMember, LegalHold
from app.models.intelligence import KnowledgeDocument, KnowledgeDocumentVersion, Report, ReportExport
from app.models.multimodal import MediaAsset, MediaEvidence, MediaProcessingRun
from app.models.storage_cleanup import StorageCleanup
from app.services.enterprise import ensure_not_held, set_db_context


async def delete_account(db, user):
    await set_db_context(db, user.id)
    memberships = (await db.scalars(select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user.id, OrganizationMember.status == "active"))).all()
    for org_id in memberships:
        await set_db_context(db, user.id, org_id)
        await ensure_not_held(db, user.id)
    await set_db_context(db, user.id)
    organizations = (await db.scalars(select(Organization).where(Organization.created_by == user.id).with_for_update())).all()
    for org in organizations:
        await set_db_context(db, user.id, org.id)
        others = await db.scalar(select(OrganizationMember.id).where(OrganizationMember.organization_id == org.id, OrganizationMember.user_id != user.id))
        if others:
            raise HTTPException(409, "Transfer ownership of shared organizations before deleting your account")
        # Removing a whole tenant also removes workspaces, regardless of hold scope.
        held = await db.scalar(select(LegalHold.id).where(LegalHold.organization_id == org.id, LegalHold.status == "active"))
        if held:
            raise HTTPException(409, "Deletion is blocked by an active legal hold")
    org_ids = [org.id for org in organizations]
    documents = (await db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.user_id == user.id).with_for_update())).all()
    if any(doc.status == "processing" for doc in documents):
        raise HTTPException(409, "Wait for knowledge processing to finish or recover before deleting your account")
    docs = [doc.id for doc in documents]
    keys = set(await db.scalars(select(KnowledgeDocumentVersion.storage_key).where(KnowledgeDocumentVersion.document_id.in_(docs))))
    keys.update(f"staging/{doc_id}" for doc_id in docs)
    for org_id in org_ids:
        await set_db_context(db, user.id, org_id)
        runs = (await db.scalars(select(MediaProcessingRun).where(MediaProcessingRun.organization_id == org_id).with_for_update())).all()
        if any(run.status == "running" for run in runs):
            raise HTTPException(409, "Wait for media processing to finish or recover before deleting your account")
        db.add(StorageCleanup(backend="knowledge_prefix", storage_key=f"media/{org_id}/"))
        keys.update(await db.scalars(select(MediaAsset.storage_key).where(MediaAsset.organization_id == org_id)))
        keys.update(await db.scalars(select(MediaEvidence.storage_key).where(MediaEvidence.organization_id == org_id)))
    for key in keys:
        if key:
            db.add(StorageCleanup(storage_key=key))
    if docs:
        db.add(StorageCleanup(backend="knowledge_prefix", storage_key=f"{user.id}/"))
    exports = await db.scalars(select(ReportExport.storage_key).join(Report).where(Report.user_id == user.id))
    for key in set(exports):
        if key:
            db.add(StorageCleanup(backend="exports", storage_key=key))
    try:
        for org in organizations:
            await set_db_context(db, user.id, org.id)
            await db.execute(delete(Organization).where(Organization.id == org.id))
        # Bulk deletion delegates all private relationships to database cascades.
        await db.execute(delete(User).where(User.id == user.id))
        await db.commit()
    except Exception as exc:
        await db.rollback()
        if isinstance(exc, IntegrityError):
            raise HTTPException(409, "Shared records still reference this account; transfer or remove them before deletion") from exc
        raise


async def process_storage_cleanup_once(sessions=None):
    from app.core.database import _get_sessionmaker
    from app.services.knowledge import storage
    from app.services.report_export import ROOT
    async with (sessions or _get_sessionmaker())() as db:
        # Failed objects cannot starve newly enqueued cleanup requests.
        rows = (await db.scalars(select(StorageCleanup).order_by(StorageCleanup.attempts, StorageCleanup.created_at).limit(50).with_for_update(skip_locked=True))).all()
        for row in rows:
            try:
                if row.backend == "exports":
                    path = Path(row.storage_key).resolve()
                    if ROOT.resolve() not in path.parents:
                        raise ValueError("Export path is outside the managed export directory")
                    await asyncio.to_thread(path.unlink, missing_ok=True)
                elif row.backend == "knowledge_prefix":
                    await asyncio.to_thread(storage.remove_prefix, row.storage_key)
                elif row.backend == "knowledge":
                    await asyncio.to_thread(storage.remove, row.storage_key)
                else:
                    raise ValueError("Unknown storage cleanup backend")
                await db.delete(row)
            except Exception as exc:
                row.attempts += 1
                row.error_message = type(exc).__name__ + ": storage cleanup failed"
        await db.commit()
        return len(rows)
