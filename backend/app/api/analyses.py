import asyncio,json
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.intelligence import Analysis
from app.schemas.analyses import AnalysisRequest,RegenerateRequest
from app.services.analysis_service import create_analysis,serialize
router=APIRouter(prefix="/api/v1/analyses",tags=["AI Analyses"])
def sse(event,data):return f"event: {event}\ndata: {json.dumps(data,ensure_ascii=False,default=str)}\n\n"
@router.post("")
async def create(payload:AnalysisRequest,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)): return await serialize(db,await create_analysis(db,user.id,payload))
@router.post("/stream")
async def stream(payload:AnalysisRequest,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    async def events():
        yield sse("progress",{"stage":"evidence","percent":20,"message":"正在核验证据范围"})
        try:
            item=await create_analysis(db,user.id,payload);await db.commit();data=await serialize(db,item)
            text=data["summary"]
            for part in [text[i:i+24] for i in range(0,len(text),24)]:yield sse("chunk",part);await asyncio.sleep(0)
            yield sse("result",data)
        except HTTPException as exc: yield sse("error",{"message":exc.detail})
        except Exception: yield sse("error",{"message":"模型分析失败，原始事件和来源数据未受影响"})
    return StreamingResponse(events(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
@router.get("/{analysis_id}")
async def detail(analysis_id:str,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    item=await db.scalar(select(Analysis).where(Analysis.id==analysis_id,Analysis.user_id==user.id));
    if not item: raise HTTPException(404,"分析不存在")
    return await serialize(db,item)
@router.post("/{analysis_id}/regenerate")
async def regenerate(analysis_id:str,payload:RegenerateRequest,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    old=await db.scalar(select(Analysis).where(Analysis.id==analysis_id,Analysis.user_id==user.id));
    if not old: raise HTTPException(404,"分析不存在")
    req=AnalysisRequest(analysis_type=old.analysis_type,event_ids=[old.event_id] if old.event_id else [],content_ids=[])
    return await serialize(db,await create_analysis(db,user.id,req,old,payload.instruction))
