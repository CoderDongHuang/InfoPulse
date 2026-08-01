"""Commercial controls with immutable versions, quota gates and real webhook execution."""
import hashlib, json
from datetime import datetime, timezone
import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.commercialization import ConnectorExecution, ProductUsage, UsageEntitlement
from app.models.platform import ConnectorInstallation

PROVIDERS={"slack","teams","feishu","dingtalk"}
def checksum(value:dict)->str:return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
def period()->str:return datetime.now(timezone.utc).strftime("%Y-%m")
def connector_payload(provider:str,message:str)->dict:
    if provider in {"slack","teams"}: return {"text":message}
    if provider=="feishu": return {"msg_type":"text","content":{"text":message}}
    return {"msgtype":"text","text":{"content":message}}

async def consume_usage(db:AsyncSession,org_id:str,feature:str,quantity:int,cost_cents:int=0,dimensions:dict|None=None)->ProductUsage:
    entitlement=await db.get(UsageEntitlement,org_id)
    if entitlement and (entitlement.status!="active" or entitlement.feature_flags.get(feature) is False): raise HTTPException(402,f"Feature '{feature}' is not included in the current plan")
    row=await db.scalar(select(ProductUsage).where(ProductUsage.organization_id==org_id,ProductUsage.period==period(),ProductUsage.feature==feature).with_for_update())
    used=row.quantity if row else 0; limit=(entitlement.limits.get(feature) if entitlement else None)
    if limit is not None and used+quantity>limit: raise HTTPException(429,f"Plan limit exceeded for '{feature}'")
    if not row: row=ProductUsage(organization_id=org_id,period=period(),feature=feature,quantity=0,cost_cents=0,dimensions={});db.add(row)
    row.quantity=used+quantity;row.cost_cents=(row.cost_cents or 0)+cost_cents;row.dimensions=dimensions or row.dimensions or {}
    await db.flush();return row

async def execute_connector(db:AsyncSession,org_id:str,payload,client:httpx.AsyncClient|None=None)->ConnectorExecution:
    existing=await db.scalar(select(ConnectorExecution).where(ConnectorExecution.organization_id==org_id,ConnectorExecution.idempotency_key==payload.idempotency_key))
    if existing:return existing
    installation=await db.scalar(select(ConnectorInstallation).where(ConnectorInstallation.id==payload.installation_id,ConnectorInstallation.organization_id==org_id,ConnectorInstallation.status=="approved",ConnectorInstallation.revoked_at.is_(None)))
    if not installation: raise HTTPException(404,"Approved connector installation not found")
    if payload.provider not in PROVIDERS or installation.connector_key!=payload.provider: raise HTTPException(422,"Connector provider mismatch")
    await consume_usage(db,org_id,"connector_executions",1)
    run=ConnectorExecution(organization_id=org_id,installation_id=installation.id,action_id=payload.action_id,provider=payload.provider,idempotency_key=payload.idempotency_key,status="running");db.add(run);await db.flush()
    owned=client is None;client=client or httpx.AsyncClient(timeout=10,follow_redirects=False)
    try:
        response=await client.post(str(payload.webhook_url),json=connector_payload(payload.provider,payload.message),headers={"User-Agent":"InfoPulse-Connector/1.0"})
        run.response_code=response.status_code;run.status="succeeded" if 200<=response.status_code<300 else "failed";run.external_reference=response.headers.get("x-request-id","")[:300]
        if run.status=="failed":run.error=f"Remote endpoint returned HTTP {response.status_code}"
    except httpx.HTTPError as exc:run.status="failed";run.error=type(exc).__name__
    finally:
        if owned:await client.aclose()
    run.finished_at=datetime.now(timezone.utc);await db.flush();return run

def serialize(row):
    return {c.name:getattr(row,c.name) for c in row.__table__.columns if c.name not in {"credential_reference"}}
