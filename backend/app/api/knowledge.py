from datetime import datetime,timezone
from fastapi import APIRouter,Depends,File,Form,HTTPException,UploadFile
from sqlalchemy import func,select
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.intelligence import KnowledgeBase,KnowledgeChunk,KnowledgeDocument,KnowledgeDocumentVersion,KnowledgeProcessingRun
from app.schemas.knowledge import KnowledgeBaseCreate,KnowledgeBaseUpdate,SearchTest,WebImportCreate
from app.services.knowledge import ALLOWED,delete_document,enqueue_document,fetch_web,safe_filename,search,settings,validate_upload

router=APIRouter(prefix="/api/v1",tags=["Knowledge RAG"])
def fail(message,status=400): raise HTTPException(status,message)
async def owned_base(db,kid,uid):
    row=await db.scalar(select(KnowledgeBase).where(KnowledgeBase.id==kid,KnowledgeBase.user_id==uid,KnowledgeBase.deleted_at.is_(None)))
    if not row: fail("知识库不存在",404)
    return row
async def owned_doc(db,did,uid):
    row=await db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.id==did,KnowledgeDocument.user_id==uid,KnowledgeDocument.deleted_at.is_(None)))
    if not row: fail("文档不存在",404)
    return row
def doc_json(x):return {"id":x.id,"knowledge_base_id":x.knowledge_base_id,"filename":x.filename,"source_type":x.source_type,"source_url":x.source_url,"mime_type":x.mime_type,"byte_size":x.byte_size,"status":x.status,"active_version_id":x.active_version_id,"error_message":x.error_message,"created_at":x.created_at,"updated_at":x.updated_at}
@router.get("/knowledge/capabilities")
async def capabilities(_u:User=Depends(get_current_user)):return {"formats":list(ALLOWED),"max_file_mb":settings.KNOWLEDGE_MAX_FILE_MB,"max_files_per_upload":settings.KNOWLEDGE_MAX_FILES_PER_UPLOAD,"storage_backend":settings.KNOWLEDGE_STORAGE_BACKEND,"hybrid_search":True,"page_citations":True}
@router.get("/knowledge-bases")
async def bases(user:User=Depends(get_current_user),db=Depends(get_db)):
    rows=(await db.scalars(select(KnowledgeBase).where(KnowledgeBase.user_id==user.id,KnowledgeBase.deleted_at.is_(None)).order_by(KnowledgeBase.updated_at.desc()))).all();return [{"id":x.id,"name":x.name,"description":x.description,"created_at":x.created_at,"updated_at":x.updated_at} for x in rows]
@router.post("/knowledge-bases",status_code=201)
async def create_base(p:KnowledgeBaseCreate,user:User=Depends(get_current_user),db=Depends(get_db)):
    x=KnowledgeBase(user_id=user.id,name=p.name.strip(),description=p.description);db.add(x);await db.commit();await db.refresh(x);return {"id":x.id,"name":x.name,"description":x.description}
@router.get("/knowledge-bases/{kid}")
async def base_detail(kid:str,user:User=Depends(get_current_user),db=Depends(get_db)):
    x=await owned_base(db,kid,user.id);count=await db.scalar(select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.knowledge_base_id==kid,KnowledgeDocument.deleted_at.is_(None)));return {"id":x.id,"name":x.name,"description":x.description,"document_count":count}
@router.patch("/knowledge-bases/{kid}")
async def update_base(kid:str,p:KnowledgeBaseUpdate,user:User=Depends(get_current_user),db=Depends(get_db)):
    x=await owned_base(db,kid,user.id)
    for k,v in p.model_dump(exclude_none=True).items():setattr(x,k,v.strip() if isinstance(v,str) else v)
    await db.commit();return {"id":x.id,"name":x.name,"description":x.description}
@router.delete("/knowledge-bases/{kid}",status_code=204)
async def remove_base(kid:str,user:User=Depends(get_current_user),db=Depends(get_db)):
    x=await owned_base(db,kid,user.id);docs=(await db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.knowledge_base_id==kid,KnowledgeDocument.deleted_at.is_(None)))).all()
    for doc in docs:await delete_document(db,doc)
    x.deleted_at=datetime.now(timezone.utc);await db.commit()
@router.get("/knowledge-bases/{kid}/documents")
async def documents(kid:str,user:User=Depends(get_current_user),db=Depends(get_db)):
    await owned_base(db,kid,user.id);return [doc_json(x) for x in (await db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.knowledge_base_id==kid,KnowledgeDocument.user_id==user.id,KnowledgeDocument.deleted_at.is_(None)).order_by(KnowledgeDocument.updated_at.desc()))).all()]
@router.post("/knowledge-bases/{kid}/documents",status_code=201)
async def upload(kid:str,files:list[UploadFile]=File(...),user:User=Depends(get_current_user),db=Depends(get_db)):
    await owned_base(db,kid,user.id)
    if len(files)>settings.KNOWLEDGE_MAX_FILES_PER_UPLOAD:fail("单次上传文件过多")
    result=[]
    for file in files:
        name=safe_filename(file.filename);data=await file.read()
        try:validate_upload(name,data)
        except Exception as exc:fail(str(exc))
        doc=KnowledgeDocument(knowledge_base_id=kid,user_id=user.id,filename=name,source_type="upload",mime_type=file.content_type or "",byte_size=len(data));db.add(doc);await db.flush()
        await db.commit();await enqueue_document(doc.id,data)
        result.append(doc_json(doc))
    return result
@router.post("/knowledge-bases/{kid}/web-imports",status_code=201)
async def web_import(kid:str,p:WebImportCreate,user:User=Depends(get_current_user),db=Depends(get_db)):
    await owned_base(db,kid,user.id)
    try:name,data=await fetch_web(str(p.url))
    except Exception as exc:fail(str(exc))
    doc=KnowledgeDocument(knowledge_base_id=kid,user_id=user.id,filename=name,source_type="web",source_url=str(p.url),mime_type="text/markdown",byte_size=len(data));db.add(doc);await db.flush()
    await db.commit();await enqueue_document(doc.id,data)
    return doc_json(doc)
@router.get("/knowledge-documents/{did}")
async def document_detail(did:str,user:User=Depends(get_current_user),db=Depends(get_db)):
    doc=await owned_doc(db,did,user.id);chunks=(await db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id==did,KnowledgeChunk.version_id==doc.active_version_id).order_by(KnowledgeChunk.ordinal).limit(100))).all();runs=(await db.scalars(select(KnowledgeProcessingRun).where(KnowledgeProcessingRun.document_id==did).order_by(KnowledgeProcessingRun.created_at.desc()).limit(10))).all();return {**doc_json(doc),"chunks":[{"id":x.id,"content":x.content,"page":x.page_number,"paragraph":x.paragraph_index,"heading":x.heading} for x in chunks],"runs":[{"id":x.id,"status":x.status,"stage":x.stage,"progress":x.progress,"attempt":x.attempt,"error_message":x.error_message,"diagnostic_id":x.diagnostic_id} for x in runs]}
@router.post("/knowledge-documents/{did}/reindex")
async def reindex(did:str,user:User=Depends(get_current_user),db=Depends(get_db)):
    doc=await owned_doc(db,did,user.id)
    doc.status="queued";doc.error_message="";await db.commit();await enqueue_document(doc.id)
    return doc_json(doc)
@router.delete("/knowledge-documents/{did}",status_code=204)
async def remove_document(did:str,user:User=Depends(get_current_user),db=Depends(get_db)):await delete_document(db,await owned_doc(db,did,user.id))
@router.post("/knowledge-bases/{kid}/search-test")
async def search_test(kid:str,p:SearchTest,user:User=Depends(get_current_user),db=Depends(get_db)):
    await owned_base(db,kid,user.id);return {"query":p.query,"results":await search(db,user.id,[kid],p.query,p.limit)}
