"""Read-only audit reproductions: isolated SQLite, no application .env or network."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
from scripts.test_suites import configure

async def main(storage):
    configure(Path(storage))
    import httpx
    from fastapi import FastAPI
    from sqlalchemy import func, select, text
    from sqlalchemy.ext.asyncio import async_sessionmaker
    import app.models
    import app.core.database as database
    from app.api.reports import router
    from app.core.security import hash_password
    from app.models.user import User
    from app.models.enterprise import TenantPolicy
    from app.models.intelligence import AgentTask, ContentItem, DataSource, Report, TaskRun
    from app.services import automation as scheduler
    from app.services.auth_service import login_user
    from app.services.enterprise import provision_personal_tenant, resolve_tenant
    from app.services.stage3 import discover_data

    engine = database._get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(database.Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    results = {}
    now = datetime.now(timezone.utc)
    async with sessions() as db:
        user = User(username="audit", email="audit@example.com", password_hash=hash_password("Audit-test-12345"))
        source = DataSource(key="audit", name="Audit", source_type="rss", health_status="healthy")
        db.add_all([user, source]); await db.flush()
        uid = user.id
        for i in range(501):
            db.add(ContentItem(source_id=source.id, external_id=str(i), canonical_url=f"https://example.com/{i}",
                               title="Java JVM Spring" if i == 500 else "AI machine learning",
                               body="audit", content_hash=f"{i:064x}", content_type="article",
                               published_at=now - timedelta(seconds=i), fetched_at=now))
        await db.commit()
        discovered = await discover_data(db, uid, "java", "day")
        assert discovered["total"] == 0
        results["discover_501st_matching_item"] = {"database_matching_items": 1, "returned_total": discovered["total"], "has_more": discovered["has_more"]}
        org = await provision_personal_tenant(db, user)
        await db.flush()
        policy = await db.get(TenantPolicy, org.id)
        policy.require_sso = True; policy.require_mfa = True
        await db.commit()
        tokens = await login_user(db, "audit", "Audit-test-12345")
        context = await resolve_tenant(db, user, org.id, None)
        assert tokens.access_token and context.organization.id == org.id
        results["sso_mfa_policy"] = {"require_sso": True, "require_mfa": True, "password_login_and_tenant_access_allowed": True}
        cancelled = AgentTask(user_id=uid, name="cancelled", task_type="daily_report", status="cancelled",
                              config={"channels": ["in_app"]}, schedule={"kind": "daily", "time": "09:00"}, timezone="UTC")
        failed = AgentTask(user_id=uid, name="failed", task_type="unsupported-audit-type", max_retries=0,
                           next_run_at=now - timedelta(minutes=1), schedule={"kind": "daily", "time": "09:00"}, timezone="UTC")
        waiting = AgentTask(user_id=uid, name="waiting", task_type="keyword_monitor", high_risk=True, confirmation_status="pending",
                            next_run_at=now - timedelta(minutes=1), schedule={"kind": "daily", "time": "09:00"}, timezone="UTC")
        db.add_all([cancelled, failed, waiting]); await db.flush()
        cid, fid, wid = cancelled.id, failed.id, waiting.id
        retry = TaskRun(task_id=cid, user_id=uid, idempotency_key="audit-cancelled-retry", status="retrying", retry_at=now - timedelta(minutes=1))
        db.add(retry); await db.commit()
    with patch.object(scheduler, "_get_sessionmaker", return_value=sessions):
        await scheduler.process_due_once()
        async with sessions() as db:
            task = await db.get(AgentTask, cid)
            run = await db.scalar(select(TaskRun).where(TaskRun.task_id == cid))
            count = await db.scalar(select(func.count(Report.id)).where(Report.user_id == uid))
            assert task.status == "cancelled" and run.status == "succeeded" and count == 1
            results["cancelled_retry"] = {"task_status": task.status, "run_status": run.status, "reports_created": count}
            task = await db.get(AgentTask, wid); task.confirmation_status = "approved"; await db.commit()
        with patch.object(scheduler, "now_utc", return_value=now + timedelta(days=2)):
            await scheduler.process_due_once()
        async with sessions() as db:
            failed_runs = (await db.scalars(select(TaskRun).where(TaskRun.task_id == fid))).all()
            waiting_runs = (await db.scalars(select(TaskRun).where(TaskRun.task_id == wid))).all()
            assert len(failed_runs) == 1 and failed_runs[0].status == "dead_letter"
            assert len(waiting_runs) == 1 and waiting_runs[0].status == "awaiting_confirmation"
            results["schedule_after_terminal_failure"] = {"elapsed_days": 2, "run_count": len(failed_runs), "status": failed_runs[0].status}
            results["confirmed_run_not_resumed"] = {"confirmation_status": "approved", "run_status": waiting_runs[0].status}
    app = FastAPI(); app.include_router(router)
    async def no_database():
        yield None
    app.dependency_overrides[database.get_db] = no_database
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://audit") as client:
        response = await client.get("/api/v1/report-exports/audit/download")
        assert response.status_code in (401, 403)
        results["navigation_download_without_bearer"] = {"status": response.status_code, "body": response.json()}
    async with sessions() as db:
        fk = (await db.execute(text("PRAGMA foreign_keys"))).scalar()
        # Exercise the same ORM deletion as DELETE /auth/me, with a private report.
        user = await db.get(User, uid); await db.delete(user); await db.commit()
        count = await db.scalar(select(func.count(Report.id)).where(Report.user_id == uid))
        assert fk == 0 and count == 1
        results["sqlite_delete_cascade"] = {"foreign_keys": fk, "private_reports_after_user_delete": count}
    # Observe the real get_db finalizer's order with a failing commit.
    events = []
    class FakeSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def commit(self): events.append("commit_failed"); raise RuntimeError("audit commit failure")
        async def rollback(self): pass
        async def close(self): pass
    durability_app = FastAPI()
    from fastapi import Depends
    @durability_app.post("/write", status_code=201)
    async def write(db=Depends(database.get_db)):
        return {"created": True}
    async def send(message):
        if message["type"] == "http.response.start": events.append(f"response_{message['status']}")
        if message["type"] == "http.response.body": events.append("response_body")
    async def receive(): return {"type": "http.request", "body": b"", "more_body": False}
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "scheme": "http", "path": "/write", "raw_path": b"/write", "query_string": b"", "headers": [], "client": ("127.0.0.1", 1), "server": ("audit", 80), "root_path": ""}
    with patch.object(database, "_get_sessionmaker", return_value=FakeSession):
        try: await durability_app(scope, receive, send)
        except RuntimeError as exc:
            assert "audit commit failure" in str(exc)
    assert events.index("response_201") < events.index("commit_failed")
    results["dependency_commit_order"] = events
    await database.close_db()
    # Reproduce production-style FK enforcement without touching PostgreSQL.
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import event
    from sqlalchemy.exc import IntegrityError
    enforced = create_async_engine("sqlite+aiosqlite:///:memory:")
    @event.listens_for(enforced.sync_engine, "connect")
    def enable_fk(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
    async with enforced.begin() as conn:
        await conn.run_sync(database.Base.metadata.create_all)
    async with async_sessionmaker(enforced, expire_on_commit=False)() as db:
        user = User(username="fk-audit", email="fk-audit@example.com", password_hash="x")
        db.add(user); await db.flush()
        await provision_personal_tenant(db, user); await db.commit()
        try:
            await db.delete(user); await db.commit()
        except IntegrityError:
            await db.rollback()
            results["account_delete_with_foreign_keys"] = {"personal_tenant_owner_deletion": "blocked_by_foreign_key"}
        else:
            raise AssertionError("Expected Organization.created_by RESTRICT to block deletion")
    await enforced.dispose()
    rendered = json.dumps(results, indent=2, ensure_ascii=False)
    Path(__file__).with_suffix(".results.json").write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="infopulse-audit-") as storage:
        asyncio.run(main(storage))
