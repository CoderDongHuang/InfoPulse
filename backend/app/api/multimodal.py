"""Tenant-scoped multimodal intelligence and real-time collaboration API."""
import hashlib,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from fastapi import APIRouter,Depends,File,Form,HTTPException,Query,UploadFile,WebSocket,WebSocketDisconnect
from fastapi.responses import Response
from sqlalchemy import delete,func,select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.core.database import _get_sessionmaker,get_db
from app.dependencies import get_current_user,get_tenant_context
from app.models.enterprise import OrganizationMember,Workspace
from app.models.multimodal import *
from app.models.user import User
from app.schemas.multimodal import *
from app.services import collaboration as collab
from app.services.collaboration import apply_change,audit,digest,new_ticket,publish,verify_resource
from app.services.enterprise import TenantContext,require_permission
from app.services.knowledge import safe_filename,storage
from app.services.multimodal import MIME,perceptual_hash,settings,validate_media

router=APIRouter(prefix="/api/v1/multimodal",tags=["Multimodal intelligence"]);UTC=timezone.utc
def now():return datetime.now(UTC)
def fail(message,status=400):raise HTTPException(status,message)
def workspace(ctx,wid):
 if wid and (not ctx.workspace or ctx.workspace.id!=wid):fail("Workspace access denied",403)
def asset_view(x):return {"id":x.id,"workspace_id":x.workspace_id,"filename":x.filename,"media_type":x.media_type,"mime_type":x.mime_type,"byte_size":x.byte_size,"content_hash":x.content_hash,"perceptual_hash":x.perceptual_hash,"duplicate_of_id":x.duplicate_of_id,"status":x.status,"duration_ms":x.duration_ms,"width":x.width,"height":x.height,"copyright_status":x.copyright_status,"license_name":x.license_name,"source_url":x.source_url,"consent_confirmed":x.consent_confirmed,"safety_status":x.safety_status,"safety_findings":x.safety_findings,"error_message":x.error_message,"created_at":x.created_at}
async def owned_asset(db,ctx,aid,include_deleted=False):
 q=select(MediaAsset).where(MediaAsset.id==aid,MediaAsset.organization_id==ctx.organization.id)
 if not include_deleted:q=q.where(MediaAsset.deleted_at.is_(None))
 row=await db.scalar(q)
 if not row:fail("Media asset not found",404)
 return row
async def owned_stream(db,ctx,sid):
 row=await db.scalar(select(LiveStream).where(LiveStream.id==sid,LiveStream.organization_id==ctx.organization.id))
 if not row:fail("Live stream not found",404)
 return row
async def owned_doc(db,ctx,did):
 row=await db.scalar(select(CollaborativeDocument).where(CollaborativeDocument.id==did,CollaborativeDocument.organization_id==ctx.organization.id))
 if not row:fail("Collaborative document not found",404)
 return row
def evidence_view(x):return {"id":x.id,"ordinal":x.ordinal,"type":x.evidence_type,"text":x.text,"start_ms":x.start_ms,"end_ms":x.end_ms,"frame_number":x.frame_number,"bbox":x.bbox,"speaker":x.speaker,"confidence":x.confidence,"content_url":f"/api/v1/multimodal/evidence/{x.id}/content" if x.storage_key else None,"metadata":x.metadata_json}

@router.get("/capabilities")
async def capabilities(ctx:TenantContext=Depends(get_tenant_context)):
 require_permission(ctx,"media.read");return {"formats":sorted(MIME),"max_file_mb":settings.MEDIA_MAX_FILE_MB,"storage_backend":settings.KNOWLEDGE_STORAGE_BACKEND,"vision_configured":bool(settings.MEDIA_VISION_MODEL and settings.LLM_API_KEY),"transcription_configured":bool(settings.MEDIA_TRANSCRIPTION_MODEL and settings.LLM_API_KEY),"video_requires_ffmpeg":True,"fabricated_results":False}
@router.get("/quality/overview")
async def quality_overview(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"media.read");org=ctx.organization.id
 total=int(await db.scalar(select(func.count()).select_from(MediaProcessingRun).where(MediaProcessingRun.organization_id==org)) or 0);succeeded=int(await db.scalar(select(func.count()).select_from(MediaProcessingRun).where(MediaProcessingRun.organization_id==org,MediaProcessingRun.status=="succeeded")) or 0);failed=int(await db.scalar(select(func.count()).select_from(MediaProcessingRun).where(MediaProcessingRun.organization_id==org,MediaProcessingRun.status=="failed")) or 0);confidence=float(await db.scalar(select(func.avg(MediaEvidence.confidence)).where(MediaEvidence.organization_id==org,MediaEvidence.confidence>0)) or 0);cost=int(await db.scalar(select(func.coalesce(func.sum(MediaProcessingRun.actual_cost_cents),0)).where(MediaProcessingRun.organization_id==org)) or 0)
 return {"runs":total,"succeeded":succeeded,"failed":failed,"success_rate":round(succeeded/total,4) if total else None,"average_evidence_confidence":round(confidence,4) if confidence else None,"actual_cost_cents":cost,"empty":total==0}
@router.get("/assets")
async def assets(media_type:str|None=None,status:str|None=None,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"media.read");q=select(MediaAsset).where(MediaAsset.organization_id==ctx.organization.id,MediaAsset.deleted_at.is_(None));q=q.where(MediaAsset.workspace_id==ctx.workspace.id) if ctx.workspace else q
 if media_type:q=q.where(MediaAsset.media_type==media_type)
 if status:q=q.where(MediaAsset.status==status)
 return [asset_view(x) for x in (await db.scalars(q.order_by(MediaAsset.created_at.desc()).limit(200))).all()]
@router.post("/assets",status_code=201)
async def upload(file:UploadFile=File(...),workspace_id:str|None=Form(None),copyright_status:str=Form("unknown"),license_name:str=Form(""),source_url:str=Form(""),consent_confirmed:bool=Form(False),capture_metadata:str=Form("{}"),ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"media.upload");workspace(ctx,workspace_id);name=safe_filename(file.filename or "media");data=await file.read()
 try:kind,mime=validate_media(name,data);capture=json.loads(capture_metadata)
 except (ValueError,json.JSONDecodeError) as exc:fail(str(exc),422)
 if not isinstance(capture,dict):fail("capture_metadata must be an object",422)
 h=hashlib.sha256(data).hexdigest();existing=await db.scalar(select(MediaAsset).where(MediaAsset.organization_id==ctx.organization.id,MediaAsset.content_hash==h,MediaAsset.deleted_at.is_(None)))
 if existing:return asset_view(existing)
 phash=perceptual_hash(data) if kind=="image" else "";duplicate=await db.scalar(select(MediaAsset.id).where(MediaAsset.organization_id==ctx.organization.id,MediaAsset.perceptual_hash==phash,MediaAsset.deleted_at.is_(None))) if phash else None
 key=f"media/{ctx.organization.id}/{h[:2]}/{h}{Path(name).suffix.lower()}";storage.put(key,data);findings=[{"type":"capture_metadata","value":capture}] if capture else []
 row=MediaAsset(organization_id=ctx.organization.id,workspace_id=workspace_id,user_id=user.id,filename=name,media_type=kind,mime_type=mime,byte_size=len(data),content_hash=h,perceptual_hash=phash,duplicate_of_id=duplicate,storage_key=key,copyright_status=copyright_status,license_name=license_name,source_url=source_url,consent_confirmed=consent_confirmed,safety_findings=findings);db.add(row);await db.flush();db.add(MediaProcessingRun(organization_id=ctx.organization.id,asset_id=row.id));await db.commit();return asset_view(row)
@router.get("/assets/{asset_id}")
async def asset_detail(asset_id:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"media.read");row=await owned_asset(db,ctx,asset_id);e=(await db.scalars(select(MediaEvidence).where(MediaEvidence.asset_id==row.id).order_by(MediaEvidence.ordinal))).all();runs=(await db.scalars(select(MediaProcessingRun).where(MediaProcessingRun.asset_id==row.id).order_by(MediaProcessingRun.created_at.desc()))).all();return {**asset_view(row),"evidence":[evidence_view(x) for x in e],"runs":[{"id":x.id,"status":x.status,"stage":x.stage,"progress":x.progress,"attempt":x.attempt,"models":x.model_routes,"estimated_cost_cents":x.estimated_cost_cents,"actual_cost_cents":x.actual_cost_cents,"error_message":x.error_message} for x in runs]}
@router.get("/assets/{asset_id}/content")
async def asset_content(asset_id:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"media.read");row=await owned_asset(db,ctx,asset_id)
 if row.safety_status in {"restricted","rejected"}:fail("Media access is restricted",403)
 try:data=storage.get(row.storage_key)
 except Exception:fail("Media content unavailable",404)
 return Response(data,media_type=row.mime_type,headers={"X-Content-Type-Options":"nosniff","Content-Disposition":f'inline; filename="{safe_filename(row.filename)}"'})
@router.get("/evidence/{evidence_id}/content")
async def evidence_content(evidence_id:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"media.read");e=await db.get(MediaEvidence,evidence_id)
 if not e or e.organization_id!=ctx.organization.id or not e.storage_key:fail("Evidence content not found",404)
 await owned_asset(db,ctx,e.asset_id)
 try:return Response(storage.get(e.storage_key),media_type="image/jpeg",headers={"X-Content-Type-Options":"nosniff"})
 except Exception:fail("Evidence content unavailable",404)
@router.post("/assets/{asset_id}/retry")
async def retry(asset_id:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"media.manage");row=await owned_asset(db,ctx,asset_id)
 if row.status!="failed":fail("Only failed assets can be retried",409)
 attempt=int(await db.scalar(select(func.max(MediaProcessingRun.attempt)).where(MediaProcessingRun.asset_id==row.id)) or 0)+1;row.status="queued";row.error_message="";db.add(MediaProcessingRun(organization_id=ctx.organization.id,asset_id=row.id,attempt=attempt));return asset_view(row)
@router.post("/assets/{asset_id}/safety")
async def safety(asset_id:str,p:SafetyDecision,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"media.manage");row=await owned_asset(db,ctx,asset_id);row.safety_status=p.decision;row.safety_findings=[*row.safety_findings,{"type":"manual_decision","decision":p.decision,"note":p.note,"actor_id":user.id,"at":now().isoformat()}];return asset_view(row)
@router.delete("/assets/{asset_id}",status_code=204)
async def remove_asset(asset_id:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"media.manage");row=await owned_asset(db,ctx,asset_id);keys=[row.storage_key,*((await db.scalars(select(MediaEvidence.storage_key).where(MediaEvidence.asset_id==row.id,MediaEvidence.storage_key!=""))).all())];row.deleted_at=now();row.status="deleted";await db.execute(delete(MediaCitation).where(MediaCitation.evidence_id.in_(select(MediaEvidence.id).where(MediaEvidence.asset_id==row.id))));await db.execute(delete(MediaEvidence).where(MediaEvidence.asset_id==row.id));await db.commit()
 for key in set(keys):storage.remove(key)
@router.post("/evidence/{evidence_id}/citations",status_code=201)
async def cite(evidence_id:str,p:CitationCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"media.read");e=await db.get(MediaEvidence,evidence_id)
 if not e or e.organization_id!=ctx.organization.id:fail("Evidence not found",404)
 if p.target_type in {"report","workflow"}:await verify_resource(db,ctx,p.target_type,p.target_id)
 else:
  from app.models.intelligence import AgentMessage,Analysis,Conversation
  if p.target_type=="analysis":target=await db.scalar(select(Analysis).where(Analysis.id==p.target_id,Analysis.user_id==user.id))
  else:target=await db.scalar(select(AgentMessage).join(Conversation,Conversation.id==AgentMessage.conversation_id).where(AgentMessage.id==p.target_id,Conversation.user_id==user.id))
  if not target:fail("Citation target not found",404)
 locator={"asset_id":e.asset_id,"evidence_id":e.id,"start_ms":e.start_ms,"end_ms":e.end_ms,"frame_number":e.frame_number,"bbox":e.bbox,"speaker":e.speaker};row=MediaCitation(organization_id=ctx.organization.id,evidence_id=e.id,locator=locator,**p.model_dump());db.add(row);await db.flush();return {"id":row.id,"locator":locator}

@router.get("/live")
async def streams(ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"media.read");return [{"id":x.id,"name":x.name,"source_type":x.source_type,"status":x.status,"started_at":x.started_at,"ended_at":x.ended_at} for x in (await db.scalars(select(LiveStream).where(LiveStream.organization_id==ctx.organization.id).order_by(LiveStream.started_at.desc()))).all()]
@router.post("/live",status_code=201)
async def create_stream(p:LiveCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"media.upload");workspace(ctx,p.workspace_id);row=LiveStream(organization_id=ctx.organization.id,created_by=user.id,**p.model_dump());db.add(row);await db.flush();return {"id":row.id,"status":row.status}
@router.get("/live/{stream_id}/updates")
async def updates(stream_id:str,after:int=Query(0,ge=0),ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"media.read");await owned_stream(db,ctx,stream_id);return [{"id":x.id,"sequence":x.sequence,"type":x.update_type,"payload":x.payload,"asset_id":x.asset_id,"occurred_at":x.occurred_at} for x in (await db.scalars(select(LiveUpdate).where(LiveUpdate.stream_id==stream_id,LiveUpdate.sequence>after).order_by(LiveUpdate.sequence).limit(500))).all()]
@router.post("/live/{stream_id}/updates",status_code=201)
async def add_update(stream_id:str,p:LiveUpdateCreate,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"media.upload");stream=await owned_stream(db,ctx,stream_id)
 if stream.status!="live":fail("Live stream has ended",409)
 if p.asset_id:await owned_asset(db,ctx,p.asset_id)
 seq=int(await db.scalar(select(func.max(LiveUpdate.sequence)).where(LiveUpdate.stream_id==stream.id)) or 0)+1
 try:occurred=datetime.fromisoformat(p.occurred_at.replace("Z","+00:00")) if p.occurred_at else now()
 except ValueError:fail("Invalid occurred_at",422)
 row=LiveUpdate(organization_id=ctx.organization.id,stream_id=stream.id,sequence=seq,update_type=p.update_type,payload=p.payload,asset_id=p.asset_id,occurred_at=occurred);db.add(row);await db.flush();event={"type":"live.update","stream_id":stream.id,"sequence":seq,"payload":p.payload};await publish(f"live:{stream.id}",event);return event
@router.post("/live/{stream_id}/end")
async def end_stream(stream_id:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"media.manage");row=await owned_stream(db,ctx,stream_id);row.status="ended";row.ended_at=now();return {"id":row.id,"status":row.status}

@router.post("/collaboration/documents",status_code=201)
async def open_document(p:CollabOpen,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"collaboration.write");workspace(ctx,p.workspace_id);existing=await db.scalar(select(CollaborativeDocument).where(CollaborativeDocument.organization_id==ctx.organization.id,CollaborativeDocument.resource_type==p.resource_type,CollaborativeDocument.resource_id==p.resource_id))
 if existing:return {"id":existing.id,"version":existing.version,"snapshot":existing.snapshot}
 snapshot=await verify_resource(db,ctx,p.resource_type,p.resource_id);row=CollaborativeDocument(organization_id=ctx.organization.id,workspace_id=p.workspace_id,resource_type=p.resource_type,resource_id=p.resource_id,snapshot=snapshot,snapshot_hash=digest(snapshot),updated_by=user.id);db.add(row);await db.flush();audit(db,row,user.id,"document.opened");return {"id":row.id,"version":row.version,"snapshot":row.snapshot}
@router.get("/collaboration/documents/{document_id}")
async def document(document_id:str,ctx:TenantContext=Depends(get_tenant_context),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"collaboration.read");row=await owned_doc(db,ctx,document_id);comments=(await db.scalars(select(CollaborationComment).where(CollaborationComment.document_id==row.id).order_by(CollaborationComment.created_at))).all();return {"id":row.id,"resource_type":row.resource_type,"resource_id":row.resource_id,"version":row.version,"snapshot":row.snapshot,"updated_at":row.updated_at,"comments":[{"id":x.id,"user_id":x.user_id,"body":x.body,"anchor":x.anchor,"mentions":x.mention_user_ids,"created_at":x.created_at} for x in comments]}
@router.post("/collaboration/documents/{document_id}/changes")
async def change(document_id:str,p:ChangeCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"collaboration.write");doc=await owned_doc(db,ctx,document_id);row=await apply_change(db,doc,user.id,p);await db.commit();event={"type":f"change.{row.status}","document_id":doc.id,"change_id":row.id,"version":row.result_version,"conflict":row.conflict};await publish(doc.id,event);return event
@router.post("/collaboration/changes/{change_id}/resolve")
async def resolve(change_id:str,p:ConflictResolve,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"collaboration.write");row=await db.get(CollaborativeChange,change_id)
 if not row or row.organization_id!=ctx.organization.id:fail("Change not found",404)
 if row.status!="conflict":fail("Change is not conflicted",409)
 doc=await owned_doc(db,ctx,row.document_id)
 if p.strategy=="keep_server":row.status="discarded";audit(db,doc,user.id,"conflict.kept_server",{"change_id":row.id})
 else:
  payload=ChangeCreate(base_version=doc.version,client_id=f"resolve:{row.client_id}",client_sequence=row.client_sequence,operations=p.operations or row.operations);applied=await apply_change(db,doc,user.id,payload);row.status="resolved";row.conflict={**row.conflict,"resolution_change_id":applied.id}
 await db.commit();event={"type":"conflict.resolved","change_id":row.id,"strategy":p.strategy,"version":doc.version};await publish(doc.id,event);return event
@router.post("/collaboration/documents/{document_id}/comments",status_code=201)
async def comment(document_id:str,p:CommentCreate,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"collaboration.write");doc=await owned_doc(db,ctx,document_id)
 if p.parent_id and not await db.scalar(select(CollaborationComment.id).where(CollaborationComment.id==p.parent_id,CollaborationComment.document_id==doc.id)):fail("Parent comment not found",404)
 valid=set((await db.scalars(select(OrganizationMember.user_id).where(OrganizationMember.organization_id==ctx.organization.id,OrganizationMember.status=="active",OrganizationMember.user_id.in_(p.mention_user_ids)))).all()) if p.mention_user_ids else set()
 if valid!=set(p.mention_user_ids):fail("Mentioned user is outside this organization",422)
 row=CollaborationComment(organization_id=ctx.organization.id,document_id=doc.id,user_id=user.id,**p.model_dump());db.add(row);await db.flush();audit(db,doc,user.id,"comment.created",{"comment_id":row.id,"mentions":p.mention_user_ids});await db.commit();event={"type":"comment.created","comment_id":row.id,"user_id":user.id,"body":row.body,"mentions":row.mention_user_ids};await publish(doc.id,event);return event
@router.post("/collaboration/documents/{document_id}/ticket")
async def ticket(document_id:str,ctx:TenantContext=Depends(get_tenant_context),user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
 require_permission(ctx,"collaboration.read");doc=await owned_doc(db,ctx,document_id);token,h=new_ticket();db.add(CollaborationTicket(organization_id=ctx.organization.id,document_id=doc.id,user_id=user.id,ticket_hash=h,expires_at=now()+timedelta(seconds=60)));return {"ticket":token,"expires_in":60}

@router.websocket("/ws/collaboration/{document_id}")
async def collaboration_socket(ws:WebSocket,document_id:str,ticket:str=Query(...)):
 await ws.accept();h=hashlib.sha256(ticket.encode()).hexdigest();sessions=_get_sessionmaker();pubsub=None
 try:
  async with sessions() as db:
   row=await db.scalar(select(CollaborationTicket).where(CollaborationTicket.document_id==document_id,CollaborationTicket.ticket_hash==h,CollaborationTicket.consumed_at.is_(None)))
   expires=row.expires_at.replace(tzinfo=UTC) if row and row.expires_at.tzinfo is None else row.expires_at if row else None
   if not row or expires<=now():await ws.close(code=4401);return
   row.consumed_at=now();user_id=row.user_id;await db.commit()
  from app.core import redis as redis_module
  if redis_module.redis_client:
   pubsub=redis_module.redis_client.pubsub();await pubsub.subscribe(f"collab:{document_id}")
  await ws.send_json({"type":"connected","document_id":document_id,"user_id":user_id})
  while True:
   try:message=await __import__("asyncio").wait_for(ws.receive_json(),timeout=.25)
   except __import__("asyncio").TimeoutError:message=None
   if message:
    if message.get("type")=="ping":await ws.send_json({"type":"pong"})
    elif message.get("type")=="presence":await publish(document_id,{"type":"presence","user_id":user_id,"cursor":message.get("cursor"),"selection":message.get("selection")})
    else:await ws.send_json({"type":"error","detail":"Persistent changes must use the versioned REST endpoint"})
   if pubsub:
    event=await pubsub.get_message(ignore_subscribe_messages=True,timeout=0)
    if event:await ws.send_text(event["data"])
 except WebSocketDisconnect:pass
 finally:
  if pubsub:await pubsub.aclose()
