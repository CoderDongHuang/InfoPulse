"""Optimistic collaboration, conflict detection and Redis-backed fanout."""
import copy,hashlib,json,secrets
from datetime import datetime,timedelta,timezone
from fastapi import HTTPException
from sqlalchemy import select
from app.core.redis import redis_client
from app.models.enterprise import OrganizationMember
from app.models.intelligence import Report,ReportVersion
from app.models.multimodal import CollaborationAudit,CollaborationTicket,CollaborativeChange,CollaborativeDocument
from app.models.orchestration import Workflow,WorkflowVersion

def now():return datetime.now(timezone.utc)
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
def paths(operations):return sorted({op["path"].strip("/") for op in operations})
def overlap(left,right):return any(a==b or a.startswith(b+"/") or b.startswith(a+"/") for a in left for b in right)
def apply_operations(snapshot,operations):
 result=copy.deepcopy(snapshot)
 for op in operations:
  parts=[x for x in op["path"].strip("/").split("/") if x];cursor=result
  for key in parts[:-1]:
   if not isinstance(cursor,dict):raise ValueError("change path crosses a non-object value")
   cursor=cursor.setdefault(key,{})
  if not isinstance(cursor,dict):raise ValueError("change target is not an object")
  if op["op"]=="set":cursor[parts[-1]]=op.get("value")
  else:cursor.pop(parts[-1],None)
 return result
def audit(db,doc,actor,action,details=None):db.add(CollaborationAudit(organization_id=doc.organization_id,document_id=doc.id,actor_id=actor,action=action,details=details or {}))
async def verify_resource(db,ctx,resource_type,resource_id):
 if resource_type=="workflow":
  row=await db.get(Workflow,resource_id)
  if not row or row.organization_id!=ctx.organization.id:raise HTTPException(404,"Workflow not found")
  version=await db.get(WorkflowVersion,row.active_version_id) if row.active_version_id else None
  return {"name":row.name,"description":row.description,"graph":version.graph if version else {"nodes":[],"edges":[]}}
 report=await db.get(Report,resource_id)
 if not report:raise HTTPException(404,"Report not found")
 owner_org=await db.scalar(select(OrganizationMember.organization_id).where(OrganizationMember.user_id==report.user_id,OrganizationMember.organization_id==ctx.organization.id,OrganizationMember.status=="active"))
 if not owner_org:raise HTTPException(404,"Report not found")
 version=await db.get(ReportVersion,report.current_version_id)
 return {"title":report.title,"content_markdown":version.content_markdown if version else "","structured_content":version.structured_content if version else {},"citations":version.citations if version else []}
async def sync_resource(db,doc,user_id):
 if doc.resource_type!="report":return
 report=await db.get(Report,doc.resource_id);current=await db.get(ReportVersion,report.current_version_id);number=current.version_number+1 if current else 1;s=doc.snapshot
 version=ReportVersion(report_id=report.id,version_number=number,content_markdown=str(s.get("content_markdown","")),structured_content=s.get("structured_content",{}),citations=s.get("citations",[]),created_by=user_id);db.add(version);await db.flush();report.title=str(s.get("title",report.title))[:300];report.current_version_id=version.id
async def apply_change(db,doc,user_id,payload):
 existing=await db.scalar(select(CollaborativeChange).where(CollaborativeChange.document_id==doc.id,CollaborativeChange.client_id==payload.client_id,CollaborativeChange.client_sequence==payload.client_sequence))
 if existing:return existing
 changed=paths(payload.operations)
 if payload.base_version>doc.version:raise HTTPException(409,"Base version is ahead of server")
 if payload.base_version<doc.version:
  later=(await db.scalars(select(CollaborativeChange).where(CollaborativeChange.document_id==doc.id,CollaborativeChange.result_version>payload.base_version,CollaborativeChange.status=="applied"))).all();server_paths=[p for x in later for p in x.changed_paths]
  if overlap(changed,server_paths):
   row=CollaborativeChange(organization_id=doc.organization_id,document_id=doc.id,base_version=payload.base_version,client_id=payload.client_id,client_sequence=payload.client_sequence,operations=payload.operations,changed_paths=changed,status="conflict",conflict={"server_version":doc.version,"server_paths":sorted(set(server_paths)),"server_snapshot":doc.snapshot},created_by=user_id);db.add(row);await db.flush();audit(db,doc,user_id,"change.conflict",{"change_id":row.id,"paths":changed});return row
 try:snapshot=apply_operations(doc.snapshot,payload.operations)
 except ValueError as exc:raise HTTPException(422,str(exc))
 doc.version+=1;doc.snapshot=snapshot;doc.snapshot_hash=digest(snapshot);doc.updated_by=user_id;row=CollaborativeChange(organization_id=doc.organization_id,document_id=doc.id,base_version=payload.base_version,result_version=doc.version,client_id=payload.client_id,client_sequence=payload.client_sequence,operations=payload.operations,changed_paths=changed,status="applied",created_by=user_id);db.add(row);await db.flush();await sync_resource(db,doc,user_id);audit(db,doc,user_id,"change.applied",{"change_id":row.id,"version":doc.version,"paths":changed});return row
def new_ticket():
 token="collab_"+secrets.token_urlsafe(32);return token,hashlib.sha256(token.encode()).hexdigest()
async def publish(document_id,event):
 from app.core import redis as redis_module
 if redis_module.redis_client:
  channel=document_id if ":" in document_id else f"collab:{document_id}"
  try:await redis_module.redis_client.publish(channel,json.dumps(event,default=str,ensure_ascii=False))
  except Exception:pass
