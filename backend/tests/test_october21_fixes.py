"""Behavior regressions for the 2026-10-21 audit fixes (A02-A12)."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, AsyncMock
import httpx
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import app.models
from app.core.database import Base, get_db, install_sqlite_foreign_keys
from app.core.routing import APIRouter
from app.models.user import User
from app.models.enterprise import Organization, OrganizationMember, TenantPolicy
from app.models.intelligence import AgentTask, TaskRun, Report, KnowledgeBase, KnowledgeDocument, KnowledgeDocumentVersion, DataSource, ContentItem
from app.models.multimodal import MediaAsset, MediaProcessingRun
from app.models.storage_cleanup import StorageCleanup
from app.services.enterprise import provision_personal_tenant, resolve_tenant
from app.services.account_deletion import delete_account, process_storage_cleanup_once
from app.services import automation
from app.api.automation import task_action, retry_run
from app.services.stage3 import discover_data
from app.services.multimodal import recover_media_leases

UTC=timezone.utc

class AuditFixTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.engine=create_async_engine("sqlite+aiosqlite:///"+str(Path(self.temp.name)/"test.db"))
        install_sqlite_foreign_keys(self.engine)
        self.sessions=async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as c: await c.run_sync(Base.metadata.create_all)
        async with self.sessions() as db:
            user=User(username="auditfix",email="auditfix@example.com",password_hash="x")
            db.add(user);await db.flush();self.uid=user.id
            org=await provision_personal_tenant(db,user);self.org=org.id;await db.commit()

    async def asyncTearDown(self):
        await self.engine.dispose();self.temp.cleanup()

    async def task(self, db, **kw):
        values=dict(user_id=self.uid,name="test",task_type="daily_report",schedule={"kind":"interval","minutes":5},timezone="UTC",next_run_at=datetime.now(UTC)-timedelta(minutes=1))
        values.update(kw);task=AgentTask(**values);db.add(task);await db.flush();return task

    async def test_enforced_identity_fails_closed_and_unenforced_remains_usable(self):
        async with self.sessions() as db:
            user=await db.get(User,self.uid)
            self.assertEqual((await resolve_tenant(db,user,self.org,None)).organization.id,self.org)
            policy=await db.get(TenantPolicy,self.org);policy.require_mfa=True;await db.flush()
            with self.assertRaises(HTTPException) as raised:await resolve_tenant(db,user,self.org,None)
            self.assertEqual(raised.exception.status_code,403)

    async def test_unsupported_policy_cannot_be_enabled(self):
        from app.api.enterprise import update_policy
        from app.schemas.enterprise import PolicyUpdate
        async with self.sessions() as db:
            user=await db.get(User,self.uid);ctx=await resolve_tenant(db,user,self.org,None)
            with self.assertRaises(HTTPException) as raised:await update_policy(PolicyUpdate(require_sso=True),ctx,user,db)
            self.assertEqual(raised.exception.status_code,409)
            self.assertFalse((await db.get(TenantPolicy,self.org)).require_sso)

    async def test_offline_policy_recovery_requires_matching_owner(self):
        from scripts import identity_policy_recovery as recovery
        async with self.sessions() as db:
            policy=await db.get(TenantPolicy,self.org);policy.require_sso=True;policy.require_mfa=True;await db.commit()
        with patch.object(recovery,"_get_sessionmaker",return_value=self.sessions),patch.object(recovery,"close_db",AsyncMock()):
            with self.assertRaises(SystemExit):await recovery.recover(self.org,"wrong-owner")
            async with self.sessions() as db:self.assertTrue((await db.get(TenantPolicy,self.org)).require_sso)
            await recovery.recover(self.org,self.uid)
        async with self.sessions() as db:
            policy=await db.get(TenantPolicy,self.org)
            self.assertFalse(policy.require_sso);self.assertFalse(policy.require_mfa)

    async def test_historical_foreign_key_checker_reports_without_repair(self):
        import sqlite3
        from scripts.sqlite_integrity_check import check
        path=Path(self.temp.name)/"legacy.db"
        with sqlite3.connect(path) as db:
            db.executescript("CREATE TABLE parent(id INTEGER PRIMARY KEY); CREATE TABLE child(id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id)); INSERT INTO child VALUES(1,99);")
        result=check(path)
        self.assertFalse(result["ok"]);self.assertEqual(result["violations"][0]["table"],"child")
        with sqlite3.connect(path) as db:self.assertEqual(db.execute("SELECT parent_id FROM child").fetchone()[0],99)

    async def test_registered_account_cascades_and_cleanup_is_durable_retryable(self):
        async with self.sessions() as db:
            user=await db.get(User,self.uid);report=Report(user_id=user.id,title="private",report_type="daily")
            kb=KnowledgeBase(user_id=user.id,name="private");db.add_all([report,kb]);await db.flush()
            doc=KnowledgeDocument(user_id=user.id,knowledge_base_id=kb.id,filename="x.txt",source_type="upload");db.add(doc);await db.flush()
            db.add(KnowledgeDocumentVersion(document_id=doc.id,version_number=1,storage_key="private/test",content_hash="x"));await db.commit()
            with patch("app.services.knowledge.storage.remove") as remove:
                await delete_account(db,user);remove.assert_not_called()
            self.assertIsNone(await db.get(User,self.uid));self.assertIsNone(await db.scalar(select(Report).where(Report.id==report.id)));self.assertIsNone(await db.get(Organization,self.org))
            self.assertEqual(await db.scalar(select(func.count(StorageCleanup.id))),4)
        with patch("app.services.knowledge.storage.remove",side_effect=OSError("offline")):
            await process_storage_cleanup_once(self.sessions)
        async with self.sessions() as db:
            self.assertEqual(await db.scalar(select(func.min(StorageCleanup.attempts))),1)
        with patch("app.services.knowledge.storage.remove") as remove:
            await process_storage_cleanup_once(self.sessions);self.assertEqual(remove.call_count,2)
        async with self.sessions() as db:self.assertEqual(await db.scalar(select(func.count(StorageCleanup.id))),0)

    async def test_shared_owner_deletion_refuses_without_touching_storage(self):
        async with self.sessions() as db:
            other=User(username="member",email="member@example.com",password_hash="x");db.add(other);await db.flush()
            db.add(OrganizationMember(organization_id=self.org,user_id=other.id));await db.commit()
            with self.assertRaises(HTTPException) as raised:await delete_account(db,await db.get(User,self.uid))
            self.assertEqual(raised.exception.status_code,409)
            self.assertEqual(await db.scalar(select(func.count(StorageCleanup.id))),0)
            self.assertIsNotNone(await db.get(User,self.uid))

    async def test_commit_failure_rolls_back_account_and_cleanup(self):
        async with self.sessions() as db:
            user=await db.get(User,self.uid)
            with patch.object(db,"commit",side_effect=RuntimeError("commit unavailable")):
                with self.assertRaises(RuntimeError):await delete_account(db,user)
            await db.rollback()
        async with self.sessions() as db:
            self.assertIsNotNone(await db.get(User,self.uid));self.assertIsNotNone(await db.get(Organization,self.org))
            self.assertEqual(await db.scalar(select(func.count(StorageCleanup.id))),0)

    async def test_cancelled_and_paused_retries_cannot_execute(self):
        for state in ("cancelled","paused"):
            async with self.sessions() as db:
                task=await self.task(db,status=state);task_id=task.id
                run=TaskRun(task_id=task.id,user_id=self.uid,idempotency_key=state,status="retrying",retry_at=datetime.now(UTC)-timedelta(minutes=1));db.add(run);await db.commit();rid=run.id
            with patch.object(automation,"_get_sessionmaker",return_value=self.sessions):await automation.process_due_once()
            async with self.sessions() as db:
                self.assertEqual(await db.scalar(select(func.count(Report.id))),0)
                self.assertEqual((await db.get(TaskRun,rid)).status,"retrying")
                user=await db.get(User,self.uid)
                previous=await db.get(TaskRun,rid);previous.status="failed";await db.flush()
                with self.assertRaises(HTTPException):await retry_run(rid,user,db)

    async def test_cancel_marks_waiters_and_approved_run_is_resumed(self):
        async with self.sessions() as db:
            user=await db.get(User,self.uid);task=await self.task(db,high_risk=True,confirmation_status="pending")
            run=await automation.enqueue_run(db,task);self.assertEqual(run.status,"awaiting_confirmation")
            await task_action(task.id,"confirm",user,db);await db.commit();rid=run.id
        with patch.object(automation,"_get_sessionmaker",return_value=self.sessions):await automation.process_due_once()
        async with self.sessions() as db:
            self.assertEqual((await db.get(TaskRun,rid)).status,"succeeded")
            task=await self.task(db,status="active");run=TaskRun(task_id=task.id,user_id=self.uid,idempotency_key="cancel",status="retrying");db.add(run);await db.flush()
            await task_action(task.id,"cancel",await db.get(User,self.uid),db);await db.flush();await db.refresh(run)
            self.assertEqual(run.status,"cancelled");self.assertIsNone(run.retry_at)

    async def test_terminal_failure_does_not_pin_schedule_cursor(self):
        async with self.sessions() as db:
            task=await self.task(db,task_type="unsupported",max_retries=0);first=await automation.enqueue_run(db,task,"schedule",task.next_run_at)
            self.assertEqual(first.status,"dead_letter");self.assertGreater(task.next_run_at.replace(tzinfo=UTC),datetime.now(UTC))
            second=await automation.enqueue_run(db,task,"schedule",task.next_run_at)
            self.assertNotEqual(first.id,second.id)

    async def test_discover_includes_501st_match_and_counts_full_range(self):
        async with self.sessions() as db:
            source=DataSource(key="auditfix",name="test",source_type="rss",config={"url":"https://example.com/feed"});db.add(source);await db.flush()
            at=datetime.now(UTC)
            for n in range(501):db.add(ContentItem(source_id=source.id,external_id=str(n),content_type="article",title="Java release" if n==500 else "AI update",body="",canonical_url=f"https://example.com/{n}",published_at=at-timedelta(seconds=n),fetched_at=at,content_hash=str(n)))
            await db.commit()
            result=await discover_data(db,self.uid,"java","day",1,20)
            self.assertEqual(result["total"],1);self.assertEqual(result["items"][0]["title"],"Java release")
            all_items=await discover_data(db,self.uid,"all","day",26,20)
            self.assertEqual(all_items["total"],501);self.assertEqual(len(all_items["items"]),1);self.assertFalse(all_items["has_more"])

    async def test_expired_media_claims_requeue_but_provider_outcomes_are_unknown(self):
        async with self.sessions() as db:
            for stage in ("claimed","provider_started","metadata"):
                asset=MediaAsset(organization_id=self.org,user_id=self.uid,filename="test.png",media_type="image",mime_type="image/png",byte_size=1,content_hash=stage,storage_key=stage,status="running");db.add(asset);await db.flush()
                db.add(MediaProcessingRun(organization_id=self.org,asset_id=asset.id,status="running",stage=stage,lease_owner="dead-worker",lease_until=datetime.now(UTC)-timedelta(minutes=1)))
            await db.commit();self.assertEqual(await recover_media_leases(db),3)
            rows=(await db.scalars(select(MediaProcessingRun))).all();db.expire_all()
            rows=(await db.scalars(select(MediaProcessingRun))).all()
            self.assertEqual(sorted(r.status for r in rows),["queued","unknown","unknown"])
            self.assertEqual(await recover_media_leases(db),0)

    async def test_success_is_sent_only_after_commit_and_failure_is_500(self):
        app=FastAPI();router=APIRouter();events=[]
        @router.post("/write",status_code=201)
        async def write(db=Depends(get_db)):
            db.add(User(username="committed",email="committed@example.com",password_hash="x"));return {"ok":True}
        app.include_router(router)
        with patch("app.core.database._get_sessionmaker",return_value=self.sessions):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,raise_app_exceptions=False),base_url="http://test") as client:
                result=await client.post("/write");self.assertEqual(result.status_code,201)
                async with self.sessions() as db:self.assertIsNotNone(await db.scalar(select(User.id).where(User.username=="committed")))
                result=await client.post("/write");self.assertEqual(result.status_code,500)
        async with self.sessions() as db:self.assertEqual(await db.scalar(select(func.count(User.id)).where(User.username=="committed")),1)


    async def test_running_media_and_knowledge_block_deletion_without_cleanup(self):
        async with self.sessions() as db:
            kb=KnowledgeBase(user_id=self.uid,name="busy");db.add(kb);await db.flush()
            doc=KnowledgeDocument(user_id=self.uid,knowledge_base_id=kb.id,filename="busy.txt",source_type="upload",status="processing");db.add(doc);await db.commit()
            with self.assertRaises(HTTPException):await delete_account(db,await db.get(User,self.uid))
            self.assertEqual(await db.scalar(select(func.count(StorageCleanup.id))),0)
            doc.status="ready";await db.commit()
            asset=MediaAsset(organization_id=self.org,user_id=self.uid,filename="busy.png",media_type="image",mime_type="image/png",byte_size=1,content_hash="busy",storage_key="busy");db.add(asset);await db.flush()
            db.add(MediaProcessingRun(organization_id=self.org,asset_id=asset.id,status="running",stage="provider_started"));await db.commit()
            with self.assertRaises(HTTPException):await delete_account(db,await db.get(User,self.uid))
            self.assertEqual(await db.scalar(select(func.count(StorageCleanup.id))),0)

    async def test_provider_marker_is_durable_and_stale_worker_cannot_publish(self):
        from app.services.multimodal import process_asset
        from tests.test_multimodal import png
        async with self.sessions() as db:
            asset=MediaAsset(organization_id=self.org,user_id=self.uid,filename="x.png",media_type="image",mime_type="image/png",byte_size=1,content_hash="fence",storage_key="fence",safety_findings=[]);db.add(asset);await db.flush()
            run=MediaProcessingRun(organization_id=self.org,asset_id=asset.id,status="running",stage="claimed",lease_owner="worker-a",lease_until=datetime.now(UTC)+timedelta(minutes=30));db.add(run);await db.commit();rid=run.id
            async def provider(*args):
                async with self.sessions() as reader:
                    observed=await reader.get(MediaProcessingRun,rid)
                    self.assertEqual(observed.stage,"provider_started")
                    self.assertIsNone((await reader.get(MediaAsset,asset.id)).width)
                    observed.status="unknown";observed.lease_owner=None;await reader.commit()
                return {"summary":"stale result"}
            with patch("app.services.multimodal.storage.get",return_value=png()),patch("app.services.multimodal.route_for",AsyncMock(return_value=("fixture",1))),patch("app.services.multimodal.vision",side_effect=provider):
                with self.assertRaisesRegex(RuntimeError,"recovered"):
                    await process_asset(db,asset,run)
        async with self.sessions() as db:
            self.assertEqual((await db.get(MediaProcessingRun,rid)).status,"unknown")
            from app.models.multimodal import MediaEvidence
            self.assertEqual(await db.scalar(select(func.count(MediaEvidence.id))),0)

    async def test_stream_commit_is_explicit_and_abandoned_work_rolls_back(self):
        from starlette.responses import StreamingResponse
        app=FastAPI();router=APIRouter()
        @router.get("/stream/{commit}")
        async def stream(commit:int,db=Depends(get_db)):
            async def body():
                db.add(User(username=f"stream{commit}",email=f"stream{commit}@example.com",password_hash="x"))
                await db.flush()
                if commit:await db.commit()
                yield b"done"
            return StreamingResponse(body())
        app.include_router(router)
        with patch("app.core.database._get_sessionmaker",return_value=self.sessions):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
                self.assertEqual((await client.get("/stream/1")).text,"done")
                self.assertEqual((await client.get("/stream/0")).text,"done")
        async with self.sessions() as db:
            self.assertIsNotNone(await db.scalar(select(User.id).where(User.username=="stream1")))
            self.assertIsNone(await db.scalar(select(User.id).where(User.username=="stream0")))


    async def test_killed_media_process_recovers_to_unknown_without_provider_replay(self):
        import asyncio, subprocess, sys
        async with self.sessions() as db:
            asset=MediaAsset(organization_id=self.org,user_id=self.uid,filename="kill.png",media_type="image",mime_type="image/png",byte_size=1,content_hash="kill",storage_key="kill",safety_findings=[]);db.add(asset);await db.flush()
            run=MediaProcessingRun(organization_id=self.org,asset_id=asset.id);db.add(run);await db.commit();rid=run.id;aid=asset.id
        marker=Path(self.temp.name)/"provider-called"
        child = r"""
import asyncio,sys
from pathlib import Path
from scripts.test_suites import configure
configure(Path(sys.argv[3]).parent/'child-storage')
from unittest.mock import AsyncMock,patch
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from app.services.multimodal import process_media_once
from tests.test_multimodal import png
async def main():
    engine=create_async_engine(sys.argv[1]);sessions=async_sessionmaker(engine,expire_on_commit=False)
    async def provider(*args):
        Path(sys.argv[3]).write_text('called')
        await asyncio.Event().wait()
    with patch('app.services.multimodal.storage.get',return_value=png()),patch('app.services.multimodal.route_for',AsyncMock(return_value=('fixture',1))),patch('app.services.multimodal.vision',side_effect=provider):
        await process_media_once(sys.argv[2],sessions)
asyncio.run(main())
"""
        log=open(Path(self.temp.name)/"child.log","w")
        process=subprocess.Popen([sys.executable,"-c",child,str(self.engine.url),aid,str(marker)],stdout=log,stderr=log)
        try:
            for _ in range(600):
                if marker.exists() or process.poll() is not None:break
                await asyncio.sleep(.1)
            self.assertTrue(marker.exists(),"worker did not reach provider: "+(Path(self.temp.name)/"child.log").read_text())
            process.kill();await asyncio.to_thread(process.wait,10)
            async with self.sessions() as db:
                run=await db.get(MediaProcessingRun,rid);self.assertEqual(run.stage,"provider_started")
                run.lease_until=datetime.now(UTC)-timedelta(seconds=1);await db.commit()
                self.assertEqual(await recover_media_leases(db),1)
            from app.services.multimodal import process_media_once
            with patch("app.services.multimodal.vision",AsyncMock()) as provider:
                self.assertFalse(await process_media_once(aid,self.sessions));provider.assert_not_awaited()
            async with self.sessions() as db:self.assertEqual((await db.get(MediaProcessingRun,rid)).status,"unknown")
        finally:
            if process.poll() is None:process.kill();await asyncio.to_thread(process.wait,10)
            log.close()
