import hashlib,json
from datetime import datetime,timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.trusted_ecosystem import *
FORBIDDEN={"raw_text","body","content","email","phone","user_id","username","secret","token","password","url"}
def digest(v)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
def sign(v,scope:str)->str:return digest({"scope":scope,"value":v})
def view(x):return {c.name:getattr(x,c.name) for c in x.__table__.columns}
def assert_sanitized(value,path="payload"):
 if isinstance(value,dict):
  for k,v in value.items():
   if k.lower() in FORBIDDEN:raise HTTPException(422,f"Federated payload contains forbidden field: {path}.{k}")
   assert_sanitized(v,f"{path}.{k}")
 elif isinstance(value,list):
  for i,v in enumerate(value):assert_sanitized(v,f"{path}[{i}]")
async def create_envelope(db:AsyncSession,org_id:str,p):
 old=await db.scalar(select(ExchangeEnvelope).where(ExchangeEnvelope.organization_id==org_id,ExchangeEnvelope.idempotency_key==p.idempotency_key));
 if old:return old
 a=await db.scalar(select(FederationAgreement).where(FederationAgreement.id==p.agreement_id,FederationAgreement.organization_id==org_id,FederationAgreement.status=="active"))
 if not a:raise HTTPException(404,"Active federation agreement not found")
 if p.metric_key not in a.allowed_metrics:raise HTTPException(403,"Metric is not allowed by the federation agreement")
 cohort=int(p.privacy.get("cohort_size",0));
 if cohort<a.minimum_cohort:raise HTTPException(422,"Federated cohort is below the agreement minimum")
 assert_sanitized(p.aggregate);assert_sanitized(p.evidence_summary)
 payload={"agreement_id":a.id,"recipient":a.partner_organization_id,"metric":p.metric_key,"aggregate":p.aggregate,"evidence":p.evidence_summary,"privacy":p.privacy}
 x=ExchangeEnvelope(organization_id=org_id,agreement_id=a.id,recipient_organization_id=a.partner_organization_id,metric_key=p.metric_key,aggregate=p.aggregate,evidence_summary=p.evidence_summary,privacy=p.privacy,idempotency_key=p.idempotency_key,signature=sign(payload,"federation"));db.add(x);await db.flush();return x
async def withdraw_contract(db:AsyncSession,org_id:str,cid:str):
 c=await db.scalar(select(DataContract).where(DataContract.id==cid,DataContract.organization_id==org_id).with_for_update())
 if not c:raise HTTPException(404,"Data contract not found")
 c.status="withdrawn";c.withdrawal_generation+=1
 agreements=(await db.scalars(select(FederationAgreement).where(FederationAgreement.organization_id==org_id,FederationAgreement.purpose==c.purpose,FederationAgreement.status=="active"))).all()
 for a in agreements:
  a.status="suspended";rows=(await db.scalars(select(ExchangeEnvelope).where(ExchangeEnvelope.agreement_id==a.id,ExchangeEnvelope.status=="available"))).all()
  for row in rows:row.status="withdrawn";row.withdrawn_at=datetime.now(timezone.utc)
 await db.flush();return c
async def append_responsibility(db:AsyncSession,org_id:str,user_id:str,p):
 prev=await db.scalar(select(ResponsibilityEvent).where(ResponsibilityEvent.organization_id==org_id,ResponsibilityEvent.subject_type==p.subject_type,ResponsibilityEvent.subject_id==p.subject_id).order_by(ResponsibilityEvent.created_at.desc(),ResponsibilityEvent.id.desc()))
 ph=digest(p.payload);previous=prev.chain_hash if prev else "";chain=sign({"previous":previous,"event":p.event_type,"payload":ph,"actor":user_id},"responsibility")
 x=ResponsibilityEvent(organization_id=org_id,subject_type=p.subject_type,subject_id=p.subject_id,event_type=p.event_type,actor_id=user_id,payload_hash=ph,previous_hash=previous,chain_hash=chain);db.add(x);await db.flush();return x
def transition_order(order:MarketplaceOrder,product:IntelligenceProduct,p):
 allowed={"authorized":{"deliver"},"delivered":{"settle","refund","dispute"},"settled":{"refund","dispute"},"disputed":{"refund"}}
 if p.action not in allowed.get(order.status,set()):raise HTTPException(409,f"Cannot {p.action} an order in {order.status} state")
 if p.action=="deliver":order.status="delivered";order.delivery_receipt={**p.receipt,"checksum":digest(p.receipt)}
 elif p.action=="settle":
  seller=round(order.amount_cents*product.revenue_share_percent/100);order.status="settled";order.settlement={"seller_cents":seller,"platform_cents":order.amount_cents-seller,"total_cents":order.amount_cents}
 elif p.action=="dispute":order.status="disputed"
 else:order.status="refunded";order.settlement={**order.settlement,"refund_cents":order.amount_cents,"reason":p.reason}
 return order
def secure_aggregate(values:list[float],kind:str)->dict:
 if not values:raise HTTPException(422,"Federated computation requires inputs")
 total=sum(values);return {"value":total/len(values) if kind=="secure_average" else total,"participant_count":len(values),"individual_values_discarded":True}
def trust_score(quality:float,reliability:float,penalty:float)->float:return max(0,min(100,round(quality*.55+reliability*.45-penalty,2)))
