from datetime import datetime,timezone
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func,select
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.intelligence import Analysis,AnalysisCitation,AgentMessage,ContentItem,Conversation,DataSource,EventContent,Favorite,MessageCitation,Report,ReportExport,ReportVersion
from app.schemas.reports import ExportCreate,ReportCreate,ReportUpdate,RewriteRequest,VersionCreate
from app.services.report_export import export_report
from app.core.llm import complete_chat,llm_is_configured
router=APIRouter(prefix="/api/v1",tags=["Reports"])
TEMPLATES=[("daily","日报"),("weekly","周报"),("event","事件报告"),("industry","行业报告"),("executive","领导简报"),("risk","风险报告")]
async def owned(db,rid,uid):
 r=await db.scalar(select(Report).where(Report.id==rid,Report.user_id==uid,Report.deleted_at.is_(None)))
 if not r:raise HTTPException(404,"报告不存在")
 return r
async def source_ids(db,user_id,config):
 ids=set(config.get("content_ids",[]));event_ids=config.get("event_ids",[])
 if event_ids:ids.update((await db.scalars(select(EventContent.content_item_id).where(EventContent.event_id.in_(event_ids)))).all())
 if config.get("include_favorites"):ids.update((await db.scalars(select(Favorite.target_id).where(Favorite.user_id==user_id,Favorite.target_type=="content"))).all())
 if config.get("analysis_ids"):
  allowed=(await db.scalars(select(Analysis.id).where(Analysis.id.in_(config["analysis_ids"]),Analysis.user_id==user_id))).all();ids.update((await db.scalars(select(AnalysisCitation.content_item_id).where(AnalysisCitation.analysis_id.in_(allowed)))).all())
 if config.get("message_ids"):
  allowed=(await db.scalars(select(AgentMessage.id).where(AgentMessage.id.in_(config["message_ids"]),AgentMessage.conversation_id.in_(select(Conversation.id).where(Conversation.user_id==user_id))))).all();ids.update((await db.scalars(select(MessageCitation.content_item_id).where(MessageCitation.message_id.in_(allowed)))).all())
 return list(ids)
@router.get("/report-templates")
async def templates(_u:User=Depends(get_current_user)):return [{"id":k,"name":v,"outline":["摘要","关键发现","影响与建议","来源引用"]} for k,v in TEMPLATES]
@router.get("/reports")
async def listing(user:User=Depends(get_current_user),db=Depends(get_db)):return [{"id":r.id,"title":r.title,"report_type":r.report_type,"status":r.status,"updated_at":r.updated_at} for r in (await db.scalars(select(Report).where(Report.user_id==user.id,Report.deleted_at.is_(None)).order_by(Report.updated_at.desc()))).all()]
@router.post("/reports",status_code=201)
async def create(p:ReportCreate,user:User=Depends(get_current_user),db=Depends(get_db)):
 ids=await source_ids(db,user.id,p.source_config);rows=(await db.execute(select(ContentItem,DataSource).join(DataSource).where(ContentItem.id.in_(ids),ContentItem.deleted_at.is_(None)))).all() if ids else [];citations=[{"content_id":x.id,"title":x.title,"source":s.name,"url":x.canonical_url,"quote":(x.body or x.title)[:400]} for x,s in rows];body="\n".join(f"- {x.title} [{i+1}]" for i,(x,_) in enumerate(rows));r=Report(user_id=user.id,title=p.title,report_type=p.report_type,source_config=p.source_config);db.add(r);await db.flush();v=ReportVersion(report_id=r.id,version_number=1,content_markdown=f"# {p.title}\n\n## 摘要\n\n## 关键发现\n{body}\n\n## 影响与建议\n",structured_content={},citations=citations,created_by=user.id);db.add(v);await db.flush();r.current_version_id=v.id;return {"id":r.id,"version_id":v.id}
@router.post("/reports/{rid}/rewrite")
async def rewrite(rid:str,p:RewriteRequest,user:User=Depends(get_current_user),db=Depends(get_db)):
 await owned(db,rid,user.id)
 if not llm_is_configured():raise HTTPException(503,"未配置 AI 模型，无法改写")
 text=await complete_chat("只改写用户提供的文本，不添加新事实、数字或来源。",f"要求:{p.instruction}\n文本:{p.selected_text}",temperature=.2,max_tokens=2000);return {"text":text}
@router.get("/reports/{rid}")
async def detail(rid:str,user:User=Depends(get_current_user),db=Depends(get_db)):
 r=await owned(db,rid,user.id);v=await db.get(ReportVersion,r.current_version_id);return {"id":r.id,"title":r.title,"report_type":r.report_type,"status":r.status,"source_config":r.source_config,"current_version":{"id":v.id,"version_number":v.version_number,"content_markdown":v.content_markdown,"structured_content":v.structured_content,"citations":v.citations}}
@router.patch("/reports/{rid}")
async def update(rid:str,p:ReportUpdate,user:User=Depends(get_current_user),db=Depends(get_db)):
 r=await owned(db,rid,user.id)
 for k,v in p.model_dump(exclude_none=True).items():setattr(r,k,v)
 return {"id":r.id,"title":r.title,"status":r.status}
@router.delete("/reports/{rid}",status_code=204)
async def remove(rid:str,user:User=Depends(get_current_user),db=Depends(get_db)):(await owned(db,rid,user.id)).deleted_at=datetime.now(timezone.utc)
@router.get("/reports/{rid}/versions")
async def versions(rid:str,user:User=Depends(get_current_user),db=Depends(get_db)):
 await owned(db,rid,user.id);return [{"id":v.id,"version_number":v.version_number,"created_at":v.created_at} for v in (await db.scalars(select(ReportVersion).where(ReportVersion.report_id==rid).order_by(ReportVersion.version_number.desc()))).all()]
@router.post("/reports/{rid}/versions",status_code=201)
async def save(rid:str,p:VersionCreate,user:User=Depends(get_current_user),db=Depends(get_db)):
 r=await owned(db,rid,user.id);rows=(await db.execute(select(ContentItem,DataSource).join(DataSource).where(ContentItem.id.in_(p.citation_content_ids),ContentItem.deleted_at.is_(None)))).all() if p.citation_content_ids else [];found={x.id for x,_ in rows}
 if found!=set(p.citation_content_ids):raise HTTPException(403,"报告包含不可访问或已删除的引用")
 citations=[{"content_id":x.id,"title":x.title,"source":s.name,"url":x.canonical_url,"quote":(x.body or x.title)[:400]} for x,s in rows];number=int(await db.scalar(select(func.max(ReportVersion.version_number)).where(ReportVersion.report_id==rid))or 0)+1;v=ReportVersion(report_id=rid,version_number=number,content_markdown=p.content_markdown,structured_content=p.structured_content,citations=citations,created_by=user.id);db.add(v);await db.flush();r.current_version_id=v.id;r.updated_at=datetime.now(timezone.utc);return {"id":v.id,"version_number":number,"citations":citations}
@router.post("/reports/{rid}/versions/{vid}/restore")
async def restore(rid:str,vid:str,user:User=Depends(get_current_user),db=Depends(get_db)):
 r=await owned(db,rid,user.id);v=await db.scalar(select(ReportVersion).where(ReportVersion.id==vid,ReportVersion.report_id==rid))
 if not v:raise HTTPException(404,"版本不存在")
 r.current_version_id=v.id;return {"version_id":v.id}
@router.post("/reports/{rid}/exports",status_code=201)
async def export(rid:str,p:ExportCreate,user:User=Depends(get_current_user),db=Depends(get_db)):
 r=await owned(db,rid,user.id);v=await db.get(ReportVersion,r.current_version_id);job=ReportExport(report_id=r.id,version_id=v.id,format=p.format,status="running");db.add(job);await db.flush()
 try:path=export_report(r,v,v.citations,p.format);job.storage_key=str(path);job.file_size=path.stat().st_size;job.status="ready"
 except Exception as e:job.status="failed";job.error_message=str(e)
 return {"id":job.id,"status":job.status,"format":job.format,"error_message":job.error_message}
@router.post("/report-exports/{eid}/retry")
async def retry(eid:str,user:User=Depends(get_current_user),db=Depends(get_db)):
 job=await db.scalar(select(ReportExport).join(Report).where(ReportExport.id==eid,Report.user_id==user.id))
 if not job or job.status!="failed":raise HTTPException(409,"仅失败任务可重试")
 r=await db.get(Report,job.report_id);v=await db.get(ReportVersion,job.version_id);path=export_report(r,v,v.citations,job.format);job.storage_key=str(path);job.file_size=path.stat().st_size;job.status="ready";job.error_message="";return {"id":job.id,"status":job.status}
@router.get("/report-exports/{eid}/download")
async def download(eid:str,user:User=Depends(get_current_user),db=Depends(get_db)):
 job=await db.scalar(select(ReportExport).join(Report).where(ReportExport.id==eid,Report.user_id==user.id,ReportExport.status=="ready"))
 if not job or not Path(job.storage_key).exists():raise HTTPException(404,"导出文件不存在")
 return FileResponse(job.storage_key,filename=Path(job.storage_key).name)
