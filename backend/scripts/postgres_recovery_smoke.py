"""Data-preserving migration and real worker-process recovery on disposable PostgreSQL."""
import argparse
import asyncio
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import asyncpg
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import make_url

from scripts.recovery_worker import configure

TABLES = ("users", "data_sources", "content_items", "events", "event_contents", "analyses",
          "analysis_citations", "reports", "report_versions", "knowledge_bases",
          "knowledge_documents", "knowledge_document_versions", "knowledge_chunks",
          "knowledge_processing_runs")


def audit_url(value):
    url = make_url(value)
    if (url.drivername != "postgresql+asyncpg" or url.host not in {"localhost", "127.0.0.1"}
            or url.username != "audit" or url.database != "infopulse_audit"):
        raise ValueError("Use only the local infopulse_audit test server, not a business database")
    return url


async def administer(url, name, create):
    if not re.fullmatch(r"infopulse_recovery_audit_[a-f0-9]{16}", name):
        raise ValueError("Invalid disposable database name")
    connection = await asyncpg.connect(host=url.host, port=url.port or 5432, user=url.username,
                                       password=url.password, database=url.database, timeout=10)
    try:
        await connection.execute(f'{"CREATE" if create else "DROP"} DATABASE "{name}"')
    finally:
        await connection.close()


async def phase(function, *args):
    from app.core.database import close_db
    try:
        return await function(*args)
    finally:
        await close_db()


async def seed():
    import app.models
    from app.core.database import _get_sessionmaker
    from app.models.user import User
    from app.models.intelligence import (DataSource, ContentItem, Event, EventContent, Analysis,
        AnalysisCitation, Report, ReportVersion, KnowledgeBase, KnowledgeDocument)
    from app.services.knowledge import process_document
    async with _get_sessionmaker()() as db:
        user = User(username="migration-audit", email="migration@example.com", password_hash="fixture-only")
        source = DataSource(key="migration-fixture", name="固定来源", source_type="rss", config={"fixture": True})
        db.add_all([user, source]); await db.flush()
        content = ContentItem(source_id=source.id, external_id="fixture-1", canonical_url="https://example.com/evidence",
                              title="Migration evidence", body="保留正文与引用", content_type="article", content_hash="a" * 64)
        event = Event(title="迁移验收事件", slug="migration-audit", created_by=user.id)
        base = KnowledgeBase(user_id=user.id, name="保留知识")
        db.add_all([content, event, base]); await db.flush()
        db.add(EventContent(event_id=event.id, content_item_id=content.id, is_primary=True))
        analysis = Analysis(event_id=event.id, user_id=user.id, analysis_type="summary", status="completed",
                            result={"claims": [{"text": "保留结论", "evidence": content.id}]})
        report = Report(user_id=user.id, title="保留报告", report_type="brief")
        document = KnowledgeDocument(user_id=user.id, knowledge_base_id=base.id, filename="retained.md",
                                     source_type="upload", status="queued")
        db.add_all([analysis, report, document]); await db.flush()
        db.add(AnalysisCitation(analysis_id=analysis.id, content_item_id=content.id, quote=content.body, claim_index=0))
        version = ReportVersion(report_id=report.id, version_number=1, created_by=user.id,
                                content_markdown="# 报告\n\n保留正文", citations=[{"id": content.id}])
        db.add(version); await db.flush(); report.current_version_id = version.id
        await process_document(db, document, "# 知识\n\n恢复验收 evidence".encode())
        return {"user": user.id, "base": base.id, "retained": document.id}


async def snapshot():
    from app.core.database import _get_engine
    result = {}
    async with _get_engine().connect() as connection:
        for table in TABLES:
            rows = (await connection.execute(text(f'SELECT * FROM "{table}"'))).mappings().all()
            values = [{k: v for k, v in dict(row).items() if not (
                table == "knowledge_documents" and k in {"processing_attempts", "lease_until"})} for row in rows]
            assert values, f"Fixture missing from {table}"
            encoded = json.dumps(sorted(values, key=lambda row: str(row.get("id", row))), ensure_ascii=False,
                                 default=str, sort_keys=True)
            result[table] = {"rows": len(values), "sha256": hashlib.sha256(encoded.encode()).hexdigest()}
    return result


async def queue_document(ids, name):
    from app.core.database import _get_sessionmaker
    from app.models.intelligence import KnowledgeDocument
    from app.services.knowledge import storage
    data = b"# Recovery\n\nDurable staged evidence across independent worker processes."
    async with _get_sessionmaker()() as db:
        row = KnowledgeDocument(user_id=ids["user"], knowledge_base_id=ids["base"], filename=name,
                                source_type="upload", mime_type="text/markdown", byte_size=len(data), status="queued")
        db.add(row); await db.flush(); storage.put("staging/" + row.id, data); await db.commit()
        return row.id


async def state(identifier):
    from app.core.database import _get_sessionmaker
    from app.models.intelligence import KnowledgeDocument, KnowledgeDocumentVersion, KnowledgeChunk
    async with _get_sessionmaker()() as db:
        row = await db.get(KnowledgeDocument, identifier)
        return {"status": row.status, "attempts": row.processing_attempts, "active": row.active_version_id,
                "versions": await db.scalar(select(func.count()).select_from(KnowledgeDocumentVersion).where(
                    KnowledgeDocumentVersion.document_id == identifier)),
                "chunks": await db.scalar(select(func.count()).select_from(KnowledgeChunk).where(
                    KnowledgeChunk.document_id == identifier))}


async def expire(identifier):
    from datetime import datetime, timedelta, timezone
    from app.core.database import _get_sessionmaker
    from app.models.intelligence import KnowledgeDocument
    async with _get_sessionmaker()() as db:
        await db.execute(update(KnowledgeDocument).where(KnowledgeDocument.id == identifier).values(
            lease_until=datetime.now(timezone.utc) - timedelta(seconds=1)))
        await db.commit()


def wait_for(identifier, predicate, workers):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        if any(worker.poll() is not None for worker in workers):
            raise AssertionError("Dedicated worker exited unexpectedly; inspect worker log")
        value = asyncio.run(phase(state, identifier))
        if predicate(value):
            return value
        if value["status"] == "failed":
            raise AssertionError(f"Worker failed: {value}")
        time.sleep(0.2)
    raise AssertionError(f"Worker state timed out: {value}")


def stop(worker):
    if worker.poll() is None:
        worker.kill()
    worker.wait(timeout=10)


def verify(database_url, output):
    root_url = audit_url(database_url)
    name = "infopulse_recovery_audit_" + uuid.uuid4().hex[:16]
    url = root_url.set(database=name).render_as_string(hide_password=False)
    output.mkdir(parents=True, exist_ok=True)
    result = {"completed": False, "checks": []}
    created = False
    try:
        asyncio.run(administer(root_url, name, True)); created = True
        with tempfile.TemporaryDirectory(prefix="infopulse-recovery-") as directory:
            storage = Path(directory) / "knowledge"
            configure(url, storage)
            config = Config("alembic.ini")
            command.upgrade(config, "head")
            ids = asyncio.run(phase(seed))
            before = asyncio.run(phase(snapshot))
            command.downgrade(config, "20260804_0029")
            assert asyncio.run(phase(snapshot)) == before, "Core data changed during downgrade"
            command.upgrade(config, "head")
            assert asyncio.run(phase(snapshot)) == before, "Core data changed during upgrade"
            result["retained_tables"] = before
            result["checks"].append("14 populated core tables retain rows and full stable-column digests across head -> 29 -> head")
            identifier = asyncio.run(phase(queue_document, ids, "interrupted.md"))
            marker = Path(directory) / "claim.marker"
            workers = []
            with (output / "knowledge-workers.log").open("w", encoding="utf-8") as log:
                def launch(pause=False):
                    ready = Path(directory) / f"worker-{len(workers)}.ready"
                    args = [sys.executable, "-m", "scripts.recovery_worker", "--database-url", url,
                            "--storage-path", str(storage), "--ready-marker", str(ready)]
                    if pause: args += ["--pause-marker", str(marker)]
                    child = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
                    workers.append(child)
                    deadline = time.monotonic() + 40
                    while not ready.exists() and time.monotonic() < deadline and child.poll() is None:
                        time.sleep(0.1)
                    assert ready.exists() and child.poll() is None, "Worker did not initialize"
                    return child
                try:
                    interrupted = launch(True)
                    value = wait_for(identifier, lambda row: row["status"] == "processing" and marker.exists(), [interrupted])
                    assert value["attempts"] == 1 and value["versions"] == 0
                    stop(interrupted)
                    assert (storage / "staging" / identifier).exists()
                    live_lease_worker = launch()
                    time.sleep(3)
                    assert live_lease_worker.poll() is None
                    value = asyncio.run(phase(state, identifier))
                    assert value["status"] == "processing" and value["attempts"] == 1
                    stop(live_lease_worker)
                    result["checks"].append("OS-killed claimed worker leaves durable staging; live lease is not stolen")
                    # Simulate time advancing past the production five-minute lease.
                    asyncio.run(phase(expire, identifier))
                    restarted = launch()
                    value = wait_for(identifier, lambda row: row["status"] == "ready", [restarted])
                    assert value["attempts"] == 2 and value["versions"] == 1 and value["chunks"] > 0 and value["active"]
                    deadline = time.monotonic() + 5
                    while (storage / "staging" / identifier).exists() and time.monotonic() < deadline:
                        time.sleep(0.1)
                    assert not (storage / "staging" / identifier).exists()
                    stop(restarted)
                    result["checks"].append("unmodified dedicated worker recovers expired claim once and cleans staging")
                    first, second = launch(), launch()
                    race_id = asyncio.run(phase(queue_document, ids, "competition.md"))
                    wait_for(race_id, lambda row: row["status"] == "ready", [first, second])
                    time.sleep(2)
                    value = asyncio.run(phase(state, race_id))
                    assert value["attempts"] == 1 and value["versions"] == 1 and value["chunks"] > 0
                    result["checks"].append("two independent PostgreSQL workers commit one version without duplicate claims")
                finally:
                    for worker in workers: stop(worker)
            result["completed"] = True
            result["scope"] = "revision-29 stable core data and knowledge role only; newer tables/fields are lost on downgrade; media/actions/orchestration recovery not covered"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        try:
            if created:
                asyncio.run(administer(root_url, name, False))
        finally:
            (output / "postgres-recovery.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default="postgresql+asyncpg://audit:audit-local-only@127.0.0.1:15432/infopulse_audit")
    parser.add_argument("--output", type=Path, default=Path("../acceptance-artifacts/recovery"))
    args = parser.parse_args()
    verify(args.database_url, args.output)
