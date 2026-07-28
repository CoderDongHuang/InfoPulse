"""Persistent scheduler, task execution, notification grouping and delivery."""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import smtplib
import socket
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.core.database import _get_sessionmaker
from app.models.intelligence import (
    AgentTask, ContentItem, DataSource, DeliveryAttempt, Notification,
    NotificationPreference, Report, ReportVersion, Subscription, TaskRun,
)

UTC = timezone.utc


def now_utc(): return datetime.now(UTC)


def next_run(schedule: dict, timezone_name: str, after: datetime | None = None) -> datetime:
    current = (after or now_utc()).astimezone(ZoneInfo(timezone_name))
    kind = schedule.get("kind", "daily")
    if kind == "interval":
        return ((after or now_utc()) + timedelta(minutes=max(1, int(schedule.get("minutes", 60))))).astimezone(UTC)
    hour, minute = (int(part) for part in schedule.get("time", "09:00").split(":", 1))
    candidate = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= current: candidate += timedelta(days=1)
    if kind == "weekly":
        weekday = int(schedule.get("weekday", 0))
        candidate += timedelta(days=(weekday - candidate.weekday()) % 7)
        if candidate <= current: candidate += timedelta(days=7)
    return candidate.astimezone(UTC)


def _in_quiet_hours(preference: NotificationPreference, at: datetime) -> tuple[bool, datetime | None]:
    if not preference.quiet_hours_enabled: return False, None
    local = at.astimezone(ZoneInfo(preference.timezone))
    start_h, start_m = map(int, preference.quiet_start.split(":")); end_h, end_m = map(int, preference.quiet_end.split(":"))
    start = local.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end = local.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    overnight = (start_h, start_m) >= (end_h, end_m)
    quiet = local >= start or local < end if overnight else start <= local < end
    if not quiet: return False, None
    delivery = end if local < end else end + timedelta(days=1)
    return True, delivery.astimezone(UTC)


async def preference_for(db, user_id: str) -> NotificationPreference:
    preference = await db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user_id))
    if not preference:
        preference = NotificationPreference(user_id=user_id); db.add(preference); await db.flush()
    return preference


async def create_notification(db, user_id: str, notification_type: str, title: str, body: str, *, severity="info", group_key="", payload=None, channels=None):
    preference = await preference_for(db, user_id)
    if preference.digest_enabled and group_key:
        existing = await db.scalar(select(Notification).where(Notification.user_id == user_id, Notification.group_key == group_key, Notification.status == "unread").order_by(Notification.created_at.desc()))
        if existing and existing.created_at.date() == now_utc().date():
            count = int(existing.payload.get("group_count", 1)) + 1
            existing.payload = {**existing.payload, "group_count": count}
            existing.body = f"{existing.body}\n{body}"
            return existing
    quiet, delivery_at = _in_quiet_hours(preference, now_utc())
    notification = Notification(user_id=user_id, notification_type=notification_type, title=title, body=body, severity=severity, group_key=group_key, payload=payload or {}, scheduled_delivery_at=delivery_at if quiet else now_utc())
    db.add(notification); await db.flush()
    for channel in channels or ["in_app"]:
        if channel != "in_app": db.add(DeliveryAttempt(notification_id=notification.id, channel=channel, status="pending", next_retry_at=notification.scheduled_delivery_at))
    return notification


def validate_webhook_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname: raise ValueError("Webhook must use HTTP(S)")
    if parsed.username or parsed.password: raise ValueError("Webhook credentials in URL are not allowed")
    for result in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(result[4][0])
        if not address.is_global: raise ValueError("Webhook target must resolve to a public address")


async def deliver_attempt(db, attempt: DeliveryAttempt):
    notification = await db.get(Notification, attempt.notification_id)
    preference = await preference_for(db, notification.user_id)
    try:
        if attempt.channel == "email":
            if not preference.email_enabled or not preference.email_address: raise RuntimeError("Email delivery is not configured")
            settings = get_settings()
            if not settings.SMTP_HOST or not settings.SMTP_FROM: raise RuntimeError("SMTP is not configured")
            message = EmailMessage(); message["Subject"] = notification.title; message["From"] = settings.SMTP_FROM; message["To"] = preference.email_address; message.set_content(notification.body)
            def send():
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
                    smtp.starttls()
                    if settings.SMTP_USERNAME: smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    smtp.send_message(message)
            await asyncio.to_thread(send)
        elif attempt.channel == "webhook":
            if not preference.webhook_enabled or not preference.webhook_url: raise RuntimeError("Webhook delivery is not configured")
            validate_webhook_url(preference.webhook_url)
            raw = json.dumps({"id": notification.id, "type": notification.notification_type, "title": notification.title, "body": notification.body, "payload": notification.payload}, ensure_ascii=False).encode()
            signature = hmac.new(preference.webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
            async with httpx.AsyncClient(timeout=get_settings().WEBHOOK_TIMEOUT_SECONDS, follow_redirects=False) as client:
                response = await client.post(preference.webhook_url, content=raw, headers={"Content-Type": "application/json", "X-InfoPulse-Signature": f"sha256={signature}"})
                attempt.response_code = response.status_code; response.raise_for_status()
        attempt.status = "delivered"; attempt.delivered_at = now_utc(); attempt.error_message = ""
    except Exception as exc:
        attempt.error_message = str(exc)[:2000]
        if attempt.attempt >= 3: attempt.status = "dead_letter"; attempt.next_retry_at = None
        else: attempt.status = "retrying"; attempt.attempt += 1; attempt.next_retry_at = now_utc() + timedelta(minutes=2 ** attempt.attempt)


async def _evidence(db, task: AgentTask, since: datetime):
    query = str(task.config.get("query", "")).strip()
    statement = select(ContentItem, DataSource).join(DataSource).where(ContentItem.deleted_at.is_(None), ContentItem.fetched_at >= since)
    if query:
        pattern = f"%{query}%"; statement = statement.where(or_(ContentItem.title.ilike(pattern), ContentItem.body.ilike(pattern)))
    return (await db.execute(statement.order_by(ContentItem.published_at.desc()).limit(50))).all()


async def _execute_daily_report(db, task: AgentTask, run: TaskRun):
    rows = await _evidence(db, task, task.last_run_at or (now_utc() - timedelta(days=1)))
    citations = [{"content_id": item.id, "title": item.title, "source": source.name, "url": item.canonical_url, "quote": (item.body or item.title)[:400]} for item, source in rows]
    title = f"自动日报 {now_utc().astimezone(ZoneInfo(task.timezone)).date().isoformat()}"
    report = Report(user_id=task.user_id, title=title, report_type="daily", source_config={"task_id": task.id}); db.add(report); await db.flush()
    findings = "\n".join(f"- {item.title} [{index}]" for index, (item, _) in enumerate(rows, 1)) or "本周期没有新增真实内容。"
    version = ReportVersion(report_id=report.id, version_number=1, content_markdown=f"# {title}\n\n## 摘要\n本报告由任务自动生成，共收录 {len(rows)} 条新增来源。\n\n## 关键发现\n{findings}\n\n## 影响与建议\n请结合来源引用进行人工复核。", structured_content={}, citations=citations, created_by=task.user_id)
    db.add(version); await db.flush(); report.current_version_id = version.id
    await create_notification(db, task.user_id, "report", "日报已生成", title, group_key=f"report:{task.id}", payload={"report_id": report.id, "run_id": run.id}, channels=task.config.get("channels", ["in_app"]))
    return {"report_id": report.id, "matched": len(rows)}


async def _execute_monitor(db, task: AgentTask, run: TaskRun):
    rows = await _evidence(db, task, task.last_run_at or (now_utc() - timedelta(days=1)))
    if rows:
        label = "企业" if task.task_type == "company_monitor" else "关键词"
        await create_notification(db, task.user_id, "subscription", f"{label}监控发现 {len(rows)} 条新增", "\n".join(item.title for item, _ in rows[:8]), severity="warning" if len(rows) >= 10 else "info", group_key=f"monitor:{task.id}", payload={"content_ids": [item.id for item, _ in rows], "run_id": run.id}, channels=task.config.get("channels", ["in_app"]))
    return {"matched": len(rows), "content_ids": [item.id for item, _ in rows]}


async def execute_run(db, task: AgentTask, run: TaskRun):
    running = int(await db.scalar(select(func.count(TaskRun.id)).where(TaskRun.task_id == task.id, TaskRun.status == "running")) or 0)
    if running >= task.max_concurrency and run.status != "running": return False
    if task.estimated_cost > task.cost_limit:
        run.status = "blocked"; run.error_message = "Estimated cost exceeds task cost limit"; run.finished_at = now_utc()
        await create_notification(db, task.user_id, "task", "任务已被成本上限阻止", task.name, severity="warning", group_key=f"cost:{task.id}")
        return False
    if task.high_risk and task.confirmation_status != "approved":
        run.status = "awaiting_confirmation"; run.error_message = "High-risk action requires confirmation"
        return False
    run.status = "running"; run.started_at = now_utc(); run.logs = [*run.logs, {"at": now_utc().isoformat(), "message": "Task started"}]
    try:
        if task.task_type == "daily_report": output = await _execute_daily_report(db, task, run)
        elif task.task_type in ("keyword_monitor", "company_monitor"): output = await _execute_monitor(db, task, run)
        else: raise ValueError("Unsupported task type")
        run.status = "succeeded"; run.output = output; run.cost = task.estimated_cost; run.finished_at = now_utc(); run.logs = [*run.logs, {"at": now_utc().isoformat(), "message": "Task completed"}]
        task.last_run_at = run.finished_at; task.next_run_at = next_run(task.schedule, task.timezone, run.finished_at)
    except Exception as exc:
        run.error_message = str(exc)[:4000]; run.diagnostic_id = str(uuid.uuid4()); run.logs = [*run.logs, {"at": now_utc().isoformat(), "message": run.error_message}]
        if run.attempt <= task.max_retries: run.status = "retrying"; run.retry_at = now_utc() + timedelta(minutes=2 ** run.attempt)
        else:
            run.status = "dead_letter"; run.finished_at = now_utc()
            await create_notification(db, task.user_id, "task", "任务执行失败", f"{task.name}\n诊断编号：{run.diagnostic_id}", severity="error", group_key=f"failure:{task.id}")
    return True


async def enqueue_run(db, task: AgentTask, trigger="manual", scheduled_for=None):
    scheduled = scheduled_for or now_utc()
    key = f"{task.id}:{scheduled.replace(second=0, microsecond=0).isoformat()}" if trigger == "schedule" else f"{task.id}:manual:{uuid.uuid4()}"
    existing = await db.scalar(select(TaskRun).where(TaskRun.idempotency_key == key))
    if existing: return existing
    run = TaskRun(task_id=task.id, user_id=task.user_id, idempotency_key=key, trigger=trigger, scheduled_for=scheduled)
    try:
        async with db.begin_nested():
            db.add(run)
            await db.flush()
    except IntegrityError:
        return await db.scalar(select(TaskRun).where(TaskRun.idempotency_key == key))
    await execute_run(db, task, run)
    return run


async def process_due_once():
    sessions = _get_sessionmaker(); now = now_utc()
    async with sessions() as db:
        tasks = (await db.scalars(select(AgentTask).where(AgentTask.status == "active", AgentTask.next_run_at <= now).order_by(AgentTask.next_run_at).limit(get_settings().TASK_WORKER_CONCURRENCY))).all()
        for task in tasks: await enqueue_run(db, task, "schedule", task.next_run_at)
        retries = (await db.scalars(select(TaskRun).where(TaskRun.status == "retrying", TaskRun.retry_at <= now).limit(get_settings().TASK_WORKER_CONCURRENCY))).all()
        for run in retries:
            task = await db.get(AgentTask, run.task_id); run.attempt += 1; await execute_run(db, task, run)
        attempts = (await db.scalars(select(DeliveryAttempt).where(DeliveryAttempt.status.in_(["pending", "retrying"]), DeliveryAttempt.next_retry_at <= now).limit(20))).all()
        for attempt in attempts: await deliver_attempt(db, attempt)
        await db.commit()


async def scheduler_loop(stop: asyncio.Event):
    while not stop.is_set():
        try: await process_due_once()
        except Exception as exc: print(f"[InfoPulse] Scheduler iteration failed: {exc}")
        try: await asyncio.wait_for(stop.wait(), timeout=max(5, get_settings().TASK_SCHEDULER_POLL_SECONDS))
        except asyncio.TimeoutError: pass
