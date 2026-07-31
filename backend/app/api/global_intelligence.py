"""Global intelligence and evidence-bounded decision API."""
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies import get_current_user,get_tenant_context
from app.models.global_intelligence import ContentTranslation,DecisionOption,DecisionRoom,GlobalNarrative,NarrativeSignal,Scenario
from app.models.intelligence import ContentItem,Event
from app.models.user import User
from app.schemas.global_intelligence import *
from app.services.enterprise import TenantContext,require_permission
from app.services.global_intelligence import audit,build_narratives,red_team,scenario,translate
router=APIRouter(prefix="/api/v1/global-intelligence",tags=["Global intelligence"])
def fail(m,s=400):raise HTTPException(s,m)
def ws(ctx,wid):
 if wid and (not ctx.workspace or ctx.workspace.id!=wid):fail("Workspace access denied",403)
async def event(db,eid):
 x=await db.get(Event,eid)
 if not x or x.deleted_at:fail("Event not found",404)
 return x
def trans(x):return {"id":x.id,"content_item_id":x.content_item_id,"source_language":x.source_language,"target_language":x.target_language,"title":x.translated_title,"body":x.translated_body,"quality_score":x.quality_score,"model_name":x.model_name,"status":x.status,"created_at":x.created_at}
def narrative(x):return {"id":x.id,"event_id":x.event_id,"title":x.title,"languages":x.languages,"regions":x.regions,"content_item_ids":x.content_item_ids,"entity_ids":x.entity_ids,"confidence":x.confidence,"status":x.status}
def option(x):return {"id":x.id,"title":x.title,"constraints":x.constraints,"benefits":x.benefits,"side_effects":x.side_effects,"counterfactuals":x.counterfactuals,"red_team_questions":x.red_team_questions,"evidence_content_ids":x.evidence_content_ids,"confidence":x.confidence,"status":x.status}
@router.get("/capabilities")
async def capabilities(ctx:TenantContext=Depends(get_tenant_context)):
 require_permission(ctx,"global.read");return {"translation_requires_approved_model":True,"narratives_require_cross_language_evidence":True,"scenarios_are_predictions":False,"manipulation_signals_require_human_review":True,"decision_freeze_is_immutable":True}
@router.post("/contents/{content_id}/translations",status_code=201)
async def create_translation(content_id:str,p:TranslationRequest,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"global.translate");content=await db.get(ContentItem,content_id)
 if not content or content.deleted_at:fail("Content not found",404)
 try:return trans(await translate(db,ctx.organization.id,user.id,content,p.target_language))
 except RuntimeError as exc:fail(str(exc),503)
@router.get("/contents/{content_id}/translations")
async def translations(content_id:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"global.read");return [trans(x) for x in (await db.scalars(select(ContentTranslation).where(ContentTranslation.content_item_id==content_id,ContentTranslation.organization_id==ctx.organization.id))).all()]
@router.post("/narratives/build",status_code=201)
async def create_narratives(p:NarrativeBuild,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"global.analyze");ws(ctx,p.workspace_id);await event(db,p.event_id);rows=await build_narratives(db,ctx.organization.id,p.event_id,p.workspace_id);return {"items":[narrative(x) for x in rows],"empty_reason":"No shared, cross-language evidence exists for a narrative cluster." if not rows else ""}
@router.get("/narratives")
async def narratives(event_id:str|None=None,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"global.read");q=select(GlobalNarrative).where(GlobalNarrative.organization_id==ctx.organization.id)
 if event_id:q=q.where(GlobalNarrative.event_id==event_id)
 rows=(await db.scalars(q.order_by(GlobalNarrative.created_at.desc()).limit(100))).all();signals=(await db.scalars(select(NarrativeSignal).where(NarrativeSignal.organization_id==ctx.organization.id))).all();by={}
 for x in signals:by.setdefault(x.narrative_id,[]).append({"type":x.signal_type,"severity":x.severity,"confidence":x.confidence,"evidence_content_ids":x.evidence_content_ids,"explanation":x.explanation,"status":x.status})
 return [{**narrative(x),"signals":by.get(x.id,[])} for x in rows]
@router.post("/scenarios",status_code=201)
async def create_scenario(p:ScenarioCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"global.analyze");ws(ctx,p.workspace_id);await event(db,p.event_id)
 try:x=await scenario(db,ctx.organization.id,user.id,p)
 except ValueError as exc:fail(str(exc),422)
 return {"id":x.id,"name":x.name,"assumptions":x.assumptions,"impact_chain":x.impact_chain,"risk_score":x.risk_score,"confidence":x.confidence,"evidence_content_ids":x.evidence_content_ids,"evidence_gaps":x.evidence_gaps,"status":x.status}
@router.get("/scenarios")
async def scenarios(event_id:str|None=None,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"global.read");q=select(Scenario).where(Scenario.organization_id==ctx.organization.id)
 if event_id:q=q.where(Scenario.event_id==event_id)
 return [{"id":x.id,"event_id":x.event_id,"name":x.name,"assumptions":x.assumptions,"impact_chain":x.impact_chain,"risk_score":x.risk_score,"confidence":x.confidence,"evidence_content_ids":x.evidence_content_ids,"evidence_gaps":x.evidence_gaps,"status":x.status} for x in (await db.scalars(q.order_by(Scenario.created_at.desc()).limit(100))).all()]
@router.post("/decision-rooms",status_code=201)
async def create_room(p:RoomCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"decision.write");ws(ctx,p.workspace_id);await event(db,p.event_id);x=DecisionRoom(organization_id=ctx.organization.id,workspace_id=p.workspace_id,event_id=p.event_id,name=p.name,created_by=user.id);db.add(x);await db.flush();audit(db,ctx.organization.id,x.id,user.id,"room.created",{});return {"id":x.id,"name":x.name,"status":x.status}
async def room(db,ctx,rid):
 x=await db.scalar(select(DecisionRoom).where(DecisionRoom.id==rid,DecisionRoom.organization_id==ctx.organization.id))
 if not x:fail("Decision room not found",404)
 return x
@router.get("/decision-rooms/{room_id}")
async def room_detail(room_id:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"decision.read");x=await room(db,ctx,room_id);opts=(await db.scalars(select(DecisionOption).where(DecisionOption.room_id==x.id))).all();from app.models.global_intelligence import DecisionAudit;audits=(await db.scalars(select(DecisionAudit).where(DecisionAudit.room_id==x.id).order_by(DecisionAudit.created_at.desc()))).all();return {"id":x.id,"name":x.name,"event_id":x.event_id,"status":x.status,"frozen_at":x.frozen_at,"options":[option(y) for y in opts],"audit":[{"action":y.action,"actor_id":y.actor_id,"details":y.details,"created_at":y.created_at} for y in audits]}
@router.post("/decision-rooms/{room_id}/options",status_code=201)
async def add_option(room_id:str,p:OptionCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"decision.write");r=await room(db,ctx,room_id)
 if r.status!="open":fail("Frozen decision rooms cannot be edited",409)
 valid=set((await db.scalars(select(ContentItem.id).where(ContentItem.id.in_(p.evidence_content_ids),ContentItem.deleted_at.is_(None)))).all())
 if len(valid)!=len(set(p.evidence_content_ids)):fail("One or more evidence sources are unavailable",422)
 x=DecisionOption(organization_id=ctx.organization.id,room_id=r.id,created_by=user.id,title=p.title,constraints=p.constraints,benefits=p.benefits,side_effects=p.side_effects,evidence_content_ids=sorted(valid),confidence=.6);x.red_team_questions,x.counterfactuals=await red_team(db,x);db.add(x);await db.flush();audit(db,ctx.organization.id,r.id,user.id,"option.created",{"option_id":x.id,"evidence_content_ids":x.evidence_content_ids});return option(x)
@router.post("/decision-rooms/{room_id}/freeze")
async def freeze(room_id:str,p:FreezeDecision,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"decision.freeze");r=await room(db,ctx,room_id)
 if r.status!="open":fail("Decision room is already frozen",409)
 r.status="frozen";r.frozen_at=datetime.now(timezone.utc);r.frozen_by=user.id;audit(db,ctx.organization.id,r.id,user.id,"room.frozen",{"note":p.note});return {"id":r.id,"status":r.status,"frozen_at":r.frozen_at}
