from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies import get_current_user,get_tenant_context
from app.models.trusted_ecosystem import *
from app.models.user import User
from app.schemas.trusted_ecosystem import *
from app.services.enterprise import TenantContext,require_permission
from app.services.trusted_ecosystem import *
router=APIRouter(prefix="/api/v1/trust-network",tags=["Trusted intelligence network"])
@router.get("/overview")
async def overview(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"org.read");oid=ctx.organization.id
 async def n(m):return await db.scalar(select(func.count()).select_from(m).where(m.organization_id==oid))
 return {"agreements":await n(FederationAgreement),"envelopes":await n(ExchangeEnvelope),"products":await n(IntelligenceProduct),"orders":await n(MarketplaceOrder),"artifacts":await n(SupplyArtifact),"regulatory_packs":await n(RegulatoryPack),"open_abuse_reports":await db.scalar(select(func.count()).select_from(AbuseReport).where(AbuseReport.organization_id==oid,AbuseReport.status=="open"))}
@router.post("/agreements",status_code=201)
async def agreement(p:AgreementCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"org.manage");x=FederationAgreement(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump());db.add(x);await db.flush();return view(x)
@router.post("/envelopes",status_code=201)
async def envelope(p:EnvelopeCreate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):require_permission(ctx,"benchmark.manage");return view(await create_envelope(db,ctx.organization.id,p))
@router.get("/inbox")
async def inbox(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):require_permission(ctx,"benchmark.read");rows=(await db.scalars(select(ExchangeEnvelope).where(ExchangeEnvelope.recipient_organization_id==ctx.organization.id,ExchangeEnvelope.status=="available"))).all();return [view(x) for x in rows]
@router.post("/data-contracts",status_code=201)
async def contract(p:DataContractCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"policy.manage");x=DataContract(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump());db.add(x);await db.flush();return view(x)
@router.post("/data-contracts/{cid}/withdraw")
async def withdraw(cid:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):require_permission(ctx,"policy.manage");return view(await withdraw_contract(db,ctx.organization.id,cid))
@router.post("/provenance",status_code=201)
async def provenance(p:ProvenanceCreate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"audit.export");payload={"type":p.object_type,"id":p.object_id,"version":p.version,"hash":p.content_hash};x=ProvenanceNode(organization_id=ctx.organization.id,object_type=p.object_type,object_id=p.object_id,version=p.version,content_hash=p.content_hash,signature=sign(payload,"provenance"),metadata_json=p.metadata_json);db.add(x);await db.flush()
 for pid in p.parent_ids:
  parent=await db.scalar(select(ProvenanceNode).where(ProvenanceNode.id==pid,ProvenanceNode.organization_id==ctx.organization.id));
  if not parent:raise HTTPException(404,"Provenance parent not found")
  db.add(ProvenanceEdge(organization_id=ctx.organization.id,source_node_id=parent.id,target_node_id=x.id,relation=p.relation,evidence_hash=sign({"source":parent.id,"target":x.id,"relation":p.relation},"edge")))
 await db.flush();return view(x)
@router.post("/supply-artifacts",status_code=201)
async def artifact(p:SupplyArtifactCreate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):require_permission(ctx,"agents.manage");payload=p.model_dump();verified=bool(p.attestation.get("runtime") and p.vendor_risk<=.6);x=SupplyArtifact(organization_id=ctx.organization.id,signature=sign(payload,"supply"),status="verified" if verified else "blocked",**payload);db.add(x);await db.flush();return view(x)
@router.post("/products",status_code=201)
async def product(p:ProductCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"billing.manage");x=IntelligenceProduct(organization_id=ctx.organization.id,created_by=user.id,status="active",**p.model_dump());db.add(x);await db.flush();return view(x)
@router.post("/orders",status_code=201)
async def order(p:OrderCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"billing.manage");old=await db.scalar(select(MarketplaceOrder).where(MarketplaceOrder.buyer_organization_id==ctx.organization.id,MarketplaceOrder.idempotency_key==p.idempotency_key));
 if old:return view(old)
 prod=await db.scalar(select(IntelligenceProduct).where(IntelligenceProduct.id==p.product_id,IntelligenceProduct.status=="active"));
 if not prod:raise HTTPException(404,"Active product not found")
 x=MarketplaceOrder(organization_id=prod.organization_id,buyer_organization_id=ctx.organization.id,product_id=prod.id,idempotency_key=p.idempotency_key,amount_cents=prod.price_cents,currency=prod.currency,provider_reference=p.provider_reference,created_by=user.id);db.add(x);await db.flush();return view(x)
@router.post("/orders/{oid}/transition")
async def order_transition(oid:str,p:OrderTransition,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"billing.manage")
 x=await db.scalar(select(MarketplaceOrder).where(MarketplaceOrder.id==oid,MarketplaceOrder.buyer_organization_id==ctx.organization.id).with_for_update())
 if not x:raise HTTPException(404,"Order not found")
 prod=await db.get(IntelligenceProduct,x.product_id);transition_order(x,prod,p);await db.flush();return view(x)
@router.post("/federated-computations",status_code=201)
async def compute(p:FederatedComputeCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"benchmark.manage");result=secure_aggregate(p.inputs,p.computation_type);data=p.model_dump(exclude={"inputs"});x=FederatedComputation(organization_id=ctx.organization.id,created_by=user.id,result=result,status="completed" if p.attestation.get("verified") else "review",**data);db.add(x);await db.flush();return view(x)
@router.post("/responsibility",status_code=201)
async def responsibility(p:ResponsibilityCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"audit.export");return view(await append_responsibility(db,ctx.organization.id,user.id,p))
@router.post("/regulatory-packs",status_code=201)
async def regulatory(p:RegulatoryPackCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"policy.manage");payload=p.model_dump();x=RegulatoryPack(organization_id=ctx.organization.id,created_by=user.id,signature=sign(payload,"regulatory"),status="active",**payload);db.add(x);await db.flush();return view(x)
@router.put("/trust-score")
async def score(p:TrustUpdate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):require_permission(ctx,"policy.manage");x=await db.scalar(select(TrustScore).where(TrustScore.organization_id==ctx.organization.id,TrustScore.subject_type==p.subject_type,TrustScore.subject_id==p.subject_id)) or TrustScore(organization_id=ctx.organization.id,subject_type=p.subject_type,subject_id=p.subject_id);db.add(x);x.quality=p.quality;x.reliability=p.reliability;x.abuse_penalty=p.abuse_penalty;x.score=trust_score(p.quality,p.reliability,p.abuse_penalty);x.status="trusted" if x.score>=75 else "review";await db.flush();return view(x)
@router.post("/abuse-reports",status_code=201)
async def abuse(p:AbuseCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"policy.manage");x=AbuseReport(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump());db.add(x);await db.flush();return view(x)
@router.post("/drills",status_code=201)
async def drill(p:DrillCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):require_permission(ctx,"org.manage");passed=bool(p.evidence) and p.containment_minutes is not None and p.recovery_minutes is not None;x=EcosystemDrill(organization_id=ctx.organization.id,created_by=user.id,status="passed" if passed else "failed",**p.model_dump());db.add(x);await db.flush();return view(x)
