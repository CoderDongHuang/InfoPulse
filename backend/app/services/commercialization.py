"""Commercial controls with immutable versions, quota gates and real webhook execution."""
import hashlib, json
from datetime import datetime, timezone
import httpx
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.commercialization import ConnectorExecution, ProductUsage, UsageEntitlement
from app.models.platform import ConnectorInstallation
from app.core.outbound import public_addresses, public_request

PROVIDERS={"slack","teams","microsoft_teams","feishu","dingtalk"}
def checksum(value:dict)->str:return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
def period()->str:return datetime.now(timezone.utc).strftime("%Y-%m")
def connector_payload(provider:str,message:str)->dict:
    if provider in {"slack","teams","microsoft_teams"}: return {"text":message}
    if provider=="feishu": return {"msg_type":"text","content":{"text":message}}
    return {"msgtype":"text","text":{"content":message}}

async def consume_usage(db:AsyncSession,org_id:str,feature:str,quantity:int,cost_cents:int=0,dimensions:dict|None=None)->ProductUsage:
    if quantity < 1 or cost_cents < 0:raise ValueError("Usage must be positive and cost nonnegative")
    entitlement=await db.get(UsageEntitlement,org_id)
    if entitlement and (entitlement.status!="active" or entitlement.feature_flags.get(feature) is False): raise HTTPException(402,f"Feature '{feature}' is not included in the current plan")
    if db.bind.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        from sqlalchemy.dialects.postgresql import insert
    month=period();keys=(ProductUsage.organization_id==org_id,ProductUsage.period==month,ProductUsage.feature==feature)
    await db.execute(insert(ProductUsage).values(organization_id=org_id,period=month,feature=feature,quantity=0,cost_cents=0,dimensions={}).on_conflict_do_nothing(index_elements=["organization_id","period","feature"]))
    limit=entitlement.limits.get(feature) if entitlement else None
    query=update(ProductUsage).where(*keys)
    if limit is not None:query=query.where(ProductUsage.quantity+quantity<=limit)
    values={"quantity":ProductUsage.quantity+quantity,"cost_cents":ProductUsage.cost_cents+cost_cents}
    if dimensions is not None:values["dimensions"]=dimensions
    claimed=await db.execute(query.values(**values).execution_options(synchronize_session=False))
    if claimed.rowcount!=1:raise HTTPException(429,f"Plan limit exceeded for '{feature}'")
    return await db.scalar(select(ProductUsage).where(*keys).execution_options(populate_existing=True))

async def execute_connector(db:AsyncSession,org_id:str,payload,client:httpx.AsyncClient|None=None)->ConnectorExecution:
    request_hash=checksum({"installation_id":payload.installation_id,"action_id":payload.action_id,"provider":payload.provider,"webhook_url":str(payload.webhook_url),"message":payload.message})
    existing=await db.scalar(select(ConnectorExecution).where(ConnectorExecution.organization_id==org_id,ConnectorExecution.idempotency_key==payload.idempotency_key))
    if existing:
        if existing.installation_id!=payload.installation_id or existing.provider!=payload.provider or existing.action_id!=payload.action_id or existing.request_hash!=request_hash:
            raise HTTPException(409,"Idempotency key belongs to another execution")
        return existing
    installation=await db.scalar(select(ConnectorInstallation).where(ConnectorInstallation.id==payload.installation_id,ConnectorInstallation.organization_id==org_id,ConnectorInstallation.status=="approved",ConnectorInstallation.revoked_at.is_(None)))
    if not installation: raise HTTPException(404,"Approved connector installation not found")
    if payload.action_id:
        from app.models.action_loop import ResponseAction
        action = await db.get(ResponseAction, payload.action_id)
        if not action or action.organization_id != org_id or action.workspace_id != installation.workspace_id:
            raise HTTPException(404, "Action not found in installation scope")
    if payload.provider not in PROVIDERS or installation.connector_key!=payload.provider: raise HTTPException(422,"Connector provider mismatch")
    target = installation.config.get("webhook_url")
    if not target or str(httpx.URL(target)) != str(httpx.URL(str(payload.webhook_url))):
        raise HTTPException(422,"Execution target must match the approved installation webhook_url")
    try: public_addresses(target, https_only=True, resolve_dns=False)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    run=ConnectorExecution(organization_id=org_id,installation_id=installation.id,action_id=payload.action_id,provider=payload.provider,idempotency_key=payload.idempotency_key,status="running",request_hash=request_hash)
    try:
        async with db.begin_nested():
            db.add(run);await db.flush()
    except IntegrityError:
        existing=await db.scalar(select(ConnectorExecution).where(ConnectorExecution.organization_id==org_id,ConnectorExecution.idempotency_key==payload.idempotency_key))
        if existing and existing.request_hash==request_hash:return existing
        raise HTTPException(409,"Idempotency key is being used by another execution")
    await consume_usage(db,org_id,"connector_executions",1)
    # Persist the intent before the irreversible POST. A crash cannot erase the
    # idempotency record and silently cause another send on restart.
    await db.commit()
    try:
        response=await public_request("POST",target,client=client,https_only=True,max_bytes=64_000,max_redirects=0,timeout=10,json=connector_payload(payload.provider,payload.message),headers={"User-Agent":"InfoPulse-Connector/1.0"})
        run.response_code=response.status_code;run.status="succeeded" if 200<=response.status_code<300 else "failed";run.external_reference=response.headers.get("x-request-id","")[:300]
        if run.status=="failed":run.error=f"Remote endpoint returned HTTP {response.status_code}"
        elif payload.provider in {"feishu","dingtalk"}:
            try:
                result=response.json()
                code=result.get("code",result.get("StatusCode",result.get("errcode")))
                if code is None or str(code)!="0":run.status="failed";run.error=f"Provider rejected delivery: code={code}"
            except (ValueError,AttributeError):run.status="failed";run.error="Invalid provider acknowledgement"
        elif payload.provider=="slack" and response.text.strip()!="ok":
            run.status="failed";run.error="Slack did not acknowledge delivery"
    except (httpx.HTTPError,TimeoutError) as exc:run.status="unknown";run.error=type(exc).__name__
    except ValueError as exc:run.status="failed";run.error=type(exc).__name__
    run.finished_at=datetime.now(timezone.utc);await db.flush();return run

def serialize(row):
    return {c.name:getattr(row,c.name) for c in row.__table__.columns if c.name not in {"credential_reference"}}
