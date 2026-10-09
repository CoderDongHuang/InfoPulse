from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.action_loop import ResponseAction, ActionRun, ActionReceipt, ActionStep, ImpactMeasurement, AnonymousBenchmark
from app.models.intelligence import ContentItem
from app.models.global_intelligence import DecisionRoom
from app.models.dispatch import DispatchJob
from app.services.dispatch import enqueue_dispatch
async def valid_evidence(db, org_id, ids):
    ids = sorted(set(ids)); rows = (await db.scalars(select(ContentItem.id).where(ContentItem.id.in_(ids), ContentItem.organization_id == org_id, ContentItem.deleted_at.is_(None)))).all() if ids else []
    if len(rows) != len(ids): raise ValueError("Evidence must belong to this organization and remain available")
    return ids
def serialize(a):
    return {"id":a.id,"title":a.title,"description":a.description,"status":a.status,"owner_id":a.owner_id,"event_id":a.event_id,"scenario_id":a.scenario_id,"decision_room_id":a.decision_room_id,"evidence_content_ids":a.evidence_content_ids,"risk_level":a.risk_level,"due_at":a.due_at,"sla_minutes":a.sla_minutes,"budget_cents":a.budget_cents,"spent_cents":a.spent_cents,"stop_conditions":a.stop_conditions,"created_at":a.created_at}
async def create_run(db, action, key):
    existing = await db.scalar(select(ActionRun).where(ActionRun.action_id == action.id, ActionRun.idempotency_key == key))
    if existing: return existing, False
    if action.status not in {"draft","approved"}: raise ValueError("Action is not startable")
    steps=(await db.scalars(select(ActionStep).where(ActionStep.action_id==action.id).order_by(ActionStep.sequence))).all()
    if not steps: raise ValueError("Action requires at least one executable or manual step")
    if (action.risk_level=="high" or any(s.requires_approval for s in steps)) and not action.approved_by: raise ValueError("Action requires independent approval")
    if action.stop_conditions: raise ValueError("Automatic stop-condition evaluation is not configured; review before starting")
    for identifier in action.dependency_ids:
        dependency=await db.get(ResponseAction,identifier)
        if not dependency or dependency.organization_id!=action.organization_id or dependency.status!="completed":raise ValueError("Action dependencies are not complete")
    if action.budget_cents and action.spent_cents >= action.budget_cents: raise ValueError("Action budget exceeded")
    claimed=await db.execute(update(ResponseAction).where(ResponseAction.id==action.id,ResponseAction.status.in_(["draft","approved"])).values(status="executing").execution_options(synchronize_session=False))
    if claimed.rowcount!=1:raise ValueError("Action was started concurrently; reload its runs")
    run = ActionRun(organization_id=action.organization_id, action_id=action.id, idempotency_key=key,status="queued"); db.add(run); action.status = "executing"; await db.flush(); return run, True


async def advance_action(db, run):
    if run.status not in {"queued","waiting_dispatch","waiting_receipt"}:return run
    await db.execute(update(ResponseAction).where(ResponseAction.id==run.action_id).values(status=ResponseAction.status))
    await db.refresh(run)
    if run.status not in {"queued","waiting_dispatch","waiting_receipt"}:return run
    action=await db.get(ResponseAction,run.action_id)
    if not action or action.status!="executing":
        run.status="failed";run.error_message="Action is no longer executing";run.finished_at=datetime.now(timezone.utc);return run
    steps=(await db.scalars(select(ActionStep).where(ActionStep.action_id==action.id).order_by(ActionStep.sequence))).all()
    step=None
    try:
        if not steps:raise ValueError("Action has no executable steps")
        for step in steps:
            if step.status=="completed":continue
            if step.channel=="manual":
                receipt=await db.scalar(select(ActionReceipt).where(ActionReceipt.run_id==run.id,ActionReceipt.step_id==step.id,ActionReceipt.channel=="manual"))
                if not receipt:
                    run.status="waiting_receipt";step.status="waiting_receipt";return run
                if receipt.receipt_payload.get("status")!="completed":raise ValueError("Manual receipt must explicitly confirm completion")
            else:
                if step.tool_key!="connector.notify":raise ValueError("Unsupported action executor")
                job=await enqueue_dispatch(db,organization_id=action.organization_id,workspace_id=action.workspace_id,installation_id=step.payload.get("installation_id"),message=step.payload.get("message"),key=f"action:{run.id}:{step.id}",action_id=action.id)
                if job.status in {"pending","running"}:
                    step.status="waiting_dispatch";run.status="waiting_dispatch";run.output={"dispatch_id":job.id,"step_id":step.id};return run
                if job.status!="succeeded":raise ValueError(f"Connector delivery {job.status}: {job.error}")
                if not await db.scalar(select(ActionReceipt.id).where(ActionReceipt.run_id==run.id,ActionReceipt.step_id==step.id)):
                    db.add(ActionReceipt(organization_id=action.organization_id,action_id=action.id,run_id=run.id,step_id=step.id,channel=step.channel,external_reference=job.result.get("external_reference",""),response_code=job.result.get("response_code"),receipt_payload={"status":"completed",**job.result},evidence_content_ids=action.evidence_content_ids))
            step.status="completed";step.finished_at=datetime.now(timezone.utc)
        run.status="completed";run.finished_at=datetime.now(timezone.utc);run.output={"completed_steps":len(steps)}
        action.status="completed";action.completed_at=run.finished_at
    except ValueError as exc:
        run.status="dead_letter";run.error_message=str(exc);run.finished_at=datetime.now(timezone.utc)
        action.status="blocked"
        if step:step.status="failed";step.error_message=str(exc)
    return run
