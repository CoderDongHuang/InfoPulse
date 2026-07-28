from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.intelligence import AgentTask, DeliveryAttempt, Notification, NotificationPreference, Subscription, TaskRun
from app.models.user import User
from app.schemas.automation import NotificationPreferenceUpdate, SubscriptionCreate, TaskCreate
from app.services.automation import enqueue_run, next_run, preference_for, validate_webhook_url

router = APIRouter(prefix="/api/v1", tags=["Automation"])


def subscription_data(item):
    return {"id": item.id, "name": item.name, "target_type": item.target_type, "target_id": item.target_id, "query": item.query, "filters": item.filters, "schedule": item.schedule, "timezone": item.timezone, "channels": item.channels, "enabled": item.enabled, "task_id": item.task_id, "created_at": item.created_at, "updated_at": item.updated_at}


def task_data(item):
    return {"id": item.id, "name": item.name, "task_type": item.task_type, "config": item.config, "schedule": item.schedule, "timezone": item.timezone, "status": item.status, "max_retries": item.max_retries, "max_concurrency": item.max_concurrency, "cost_limit": item.cost_limit, "estimated_cost": item.estimated_cost, "high_risk": item.high_risk, "confirmation_status": item.confirmation_status, "next_run_at": item.next_run_at, "last_run_at": item.last_run_at, "created_at": item.created_at}


def run_data(item):
    return {"id": item.id, "task_id": item.task_id, "status": item.status, "attempt": item.attempt, "trigger": item.trigger, "scheduled_for": item.scheduled_for, "started_at": item.started_at, "finished_at": item.finished_at, "retry_at": item.retry_at, "output": item.output, "logs": item.logs, "error_message": item.error_message, "diagnostic_id": item.diagnostic_id, "cost": item.cost, "created_at": item.created_at}


async def owned_task(db, task_id, user_id):
    task = await db.scalar(select(AgentTask).where(AgentTask.id == task_id, AgentTask.user_id == user_id))
    if not task: raise HTTPException(404, "任务不存在")
    return task


@router.get("/automation/templates")
async def templates(_user: User = Depends(get_current_user)):
    return [
        {"id": "daily_report", "name": "每日情报日报", "description": "按时汇总新增真实来源并生成带引用日报", "default_schedule": {"kind": "daily", "time": "09:00"}, "estimated_cost": 0.15},
        {"id": "keyword_monitor", "name": "关键词监控", "description": "发现关键词相关新增内容并通知", "default_schedule": {"kind": "interval", "minutes": 60}, "estimated_cost": 0.02},
        {"id": "company_monitor", "name": "企业监控", "description": "持续跟踪企业相关公开内容", "default_schedule": {"kind": "interval", "minutes": 60}, "estimated_cost": 0.02},
    ]


@router.get("/subscriptions")
async def list_subscriptions(user: User = Depends(get_current_user), db=Depends(get_db)):
    return [subscription_data(item) for item in (await db.scalars(select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.updated_at.desc()))).all()]


@router.post("/subscriptions", status_code=201)
async def create_subscription(payload: SubscriptionCreate, user: User = Depends(get_current_user), db=Depends(get_db)):
    data = payload.model_dump(); subscription = Subscription(user_id=user.id, **data); db.add(subscription); await db.flush()
    task_type = "daily_report" if payload.target_type == "report" else ("company_monitor" if payload.target_type == "company" else "keyword_monitor")
    high_risk = "webhook" in payload.channels
    task = AgentTask(user_id=user.id, subscription_id=subscription.id, name=payload.name, task_type=task_type, config={"query": payload.query, "filters": payload.filters, "channels": payload.channels}, schedule=payload.schedule, timezone=payload.timezone, high_risk=high_risk, confirmation_status="pending" if high_risk else "not_required", estimated_cost=.15 if task_type == "daily_report" else .02, next_run_at=next_run(payload.schedule, payload.timezone))
    db.add(task); await db.flush(); subscription.task_id = task.id
    return {**subscription_data(subscription), "task": task_data(task)}


@router.patch("/subscriptions/{subscription_id}")
async def update_subscription(subscription_id: str, enabled: bool, user: User = Depends(get_current_user), db=Depends(get_db)):
    subscription = await db.scalar(select(Subscription).where(Subscription.id == subscription_id, Subscription.user_id == user.id))
    if not subscription: raise HTTPException(404, "订阅不存在")
    subscription.enabled = enabled; subscription.updated_at = datetime.now(timezone.utc)
    if subscription.task_id:
        task = await db.get(AgentTask, subscription.task_id); task.status = "active" if enabled else "paused"
    return subscription_data(subscription)


@router.delete("/subscriptions/{subscription_id}", status_code=204)
async def delete_subscription(subscription_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    subscription = await db.scalar(select(Subscription).where(Subscription.id == subscription_id, Subscription.user_id == user.id))
    if not subscription: raise HTTPException(404, "订阅不存在")
    if subscription.task_id:
        task = await db.get(AgentTask, subscription.task_id)
        if task: await db.delete(task)
    await db.delete(subscription)


@router.get("/tasks")
async def list_tasks(user: User = Depends(get_current_user), db=Depends(get_db)):
    return [task_data(item) for item in (await db.scalars(select(AgentTask).where(AgentTask.user_id == user.id).order_by(AgentTask.created_at.desc()))).all()]


@router.post("/tasks", status_code=201)
async def create_task(payload: TaskCreate, user: User = Depends(get_current_user), db=Depends(get_db)):
    high_risk = bool(payload.config.get("channels") and "webhook" in payload.config["channels"])
    task = AgentTask(user_id=user.id, **payload.model_dump(), high_risk=high_risk, confirmation_status="pending" if high_risk else "not_required", next_run_at=next_run(payload.schedule, payload.timezone)); db.add(task); await db.flush()
    return task_data(task)


@router.get("/tasks/{task_id}/runs")
async def runs(task_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    await owned_task(db, task_id, user.id)
    return [run_data(item) for item in (await db.scalars(select(TaskRun).where(TaskRun.task_id == task_id).order_by(TaskRun.created_at.desc()).limit(100))).all()]


@router.post("/tasks/{task_id}/run", status_code=202)
async def run_now(task_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    task = await owned_task(db, task_id, user.id)
    if task.status == "cancelled": raise HTTPException(409, "已取消任务不能运行")
    run = await enqueue_run(db, task, "manual")
    return run_data(run)


@router.post("/tasks/{task_id}/{action}")
async def task_action(task_id: str, action: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    task = await owned_task(db, task_id, user.id)
    if action == "pause": task.status = "paused"
    elif action == "resume": task.status = "active"; task.next_run_at = next_run(task.schedule, task.timezone)
    elif action == "cancel": task.status = "cancelled"; task.next_run_at = None
    elif action == "confirm": task.confirmation_status = "approved"
    else: raise HTTPException(404, "未知任务操作")
    return task_data(task)


@router.post("/task-runs/{run_id}/retry", status_code=202)
async def retry_run(run_id: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    previous = await db.scalar(select(TaskRun).where(TaskRun.id == run_id, TaskRun.user_id == user.id))
    if not previous: raise HTTPException(404, "运行记录不存在")
    if previous.status not in ("dead_letter", "failed", "blocked"): raise HTTPException(409, "仅失败、死信或被阻止的任务可重试")
    task = await owned_task(db, previous.task_id, user.id); run = await enqueue_run(db, task, "retry")
    return run_data(run)


@router.get("/notifications")
async def notifications(status: str | None = None, user: User = Depends(get_current_user), db=Depends(get_db)):
    now = datetime.now(timezone.utc)
    statement = select(Notification).where(Notification.user_id == user.id, or_(Notification.scheduled_delivery_at.is_(None), Notification.scheduled_delivery_at <= now))
    if status: statement = statement.where(Notification.status == status)
    rows = (await db.scalars(statement.order_by(Notification.created_at.desc()).limit(200))).all()
    return [{"id": item.id, "type": item.notification_type, "title": item.title, "body": item.body, "severity": item.severity, "status": item.status, "payload": item.payload, "scheduled_delivery_at": item.scheduled_delivery_at, "created_at": item.created_at} for item in rows]


@router.get("/notifications/unread-count")
async def unread_count(user: User = Depends(get_current_user), db=Depends(get_db)):
    now = datetime.now(timezone.utc)
    return {"count": int(await db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.status == "unread", or_(Notification.scheduled_delivery_at.is_(None), Notification.scheduled_delivery_at <= now))) or 0)}


@router.patch("/notifications/{notification_id}")
async def update_notification(notification_id: str, status: str, user: User = Depends(get_current_user), db=Depends(get_db)):
    if status not in ("read", "archived"): raise HTTPException(422, "状态仅支持 read 或 archived")
    item = await db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id))
    if not item: raise HTTPException(404, "通知不存在")
    item.status = status; item.read_at = datetime.now(timezone.utc) if status == "read" else item.read_at
    return {"id": item.id, "status": item.status}


@router.post("/notifications/read-all")
async def read_all(user: User = Depends(get_current_user), db=Depends(get_db)):
    rows = (await db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.status == "unread"))).all()
    now = datetime.now(timezone.utc)
    for item in rows: item.status = "read"; item.read_at = now
    return {"updated": len(rows)}


@router.get("/notification-preferences")
async def get_preferences(user: User = Depends(get_current_user), db=Depends(get_db)):
    item = await preference_for(db, user.id)
    return {"timezone": item.timezone, "quiet_hours_enabled": item.quiet_hours_enabled, "quiet_start": item.quiet_start, "quiet_end": item.quiet_end, "digest_enabled": item.digest_enabled, "email_enabled": item.email_enabled, "email_address": item.email_address, "webhook_enabled": item.webhook_enabled, "webhook_url": item.webhook_url, "webhook_secret_configured": bool(item.webhook_secret)}


@router.patch("/notification-preferences")
async def update_preferences(payload: NotificationPreferenceUpdate, user: User = Depends(get_current_user), db=Depends(get_db)):
    if payload.webhook_enabled:
        try: validate_webhook_url(payload.webhook_url)
        except (ValueError, OSError) as exc: raise HTTPException(422, str(exc)) from exc
    item = await preference_for(db, user.id)
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    return await get_preferences(user, db)


@router.get("/delivery-attempts")
async def deliveries(user: User = Depends(get_current_user), db=Depends(get_db)):
    rows = (await db.execute(select(DeliveryAttempt, Notification).join(Notification).where(Notification.user_id == user.id).order_by(DeliveryAttempt.created_at.desc()).limit(100))).all()
    return [{"id": attempt.id, "notification_id": notification.id, "title": notification.title, "channel": attempt.channel, "status": attempt.status, "attempt": attempt.attempt, "response_code": attempt.response_code, "error_message": attempt.error_message, "next_retry_at": attempt.next_retry_at, "delivered_at": attempt.delivered_at} for attempt, notification in rows]
