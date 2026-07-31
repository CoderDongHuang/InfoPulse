from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.action_loop import ResponseAction, ActionRun, ActionReceipt, ActionStep, ImpactMeasurement, AnonymousBenchmark
from app.models.intelligence import ContentItem
from app.models.global_intelligence import DecisionRoom
async def valid_evidence(db, org_id, ids):
    ids = sorted(set(ids)); rows = (await db.scalars(select(ContentItem.id).where(ContentItem.id.in_(ids), ContentItem.organization_id == org_id, ContentItem.deleted_at.is_(None)))).all() if ids else []
    if len(rows) != len(ids): raise ValueError("Evidence must belong to this organization and remain available")
    return ids
def serialize(a):
    return {"id":a.id,"title":a.title,"description":a.description,"status":a.status,"owner_id":a.owner_id,"event_id":a.event_id,"scenario_id":a.scenario_id,"decision_room_id":a.decision_room_id,"evidence_content_ids":a.evidence_content_ids,"risk_level":a.risk_level,"due_at":a.due_at,"sla_minutes":a.sla_minutes,"budget_cents":a.budget_cents,"spent_cents":a.spent_cents,"stop_conditions":a.stop_conditions,"created_at":a.created_at}
async def create_run(db, action, key):
    existing = await db.scalar(select(ActionRun).where(ActionRun.action_id == action.id, ActionRun.idempotency_key == key))
    if existing: return existing, False
    if action.budget_cents and action.spent_cents >= action.budget_cents: raise ValueError("Action budget exceeded")
    run = ActionRun(organization_id=action.organization_id, action_id=action.id, idempotency_key=key); db.add(run); action.status = "executing"; await db.flush(); return run, True
