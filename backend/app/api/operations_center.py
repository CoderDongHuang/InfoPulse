from datetime import datetime,timezone,timedelta
import re
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import func,select
from app.core.database import get_db
from app.dependencies import get_current_user,require_admin
from app.models.user import User
from app.models.intelligence import ProductEvent,UserFeedback,ReleaseRecord
from app.schemas.operations import ProductEventCreate,FeedbackCreate,FeedbackUpdate,ReleaseCreate

router=APIRouter(prefix="/api/v1",tags=["Product Operations"])
SECRET=re.compile(r"(?i)(bearer\s+|api[_-]?key|password|secret|cookie|token=)")

@router.post("/product-events",status_code=202)
async def track(p:ProductEventCreate,user:User=Depends(get_current_user),db=Depends(get_db)):
    db.add(ProductEvent(user_id=user.id,**p.model_dump()));return {"accepted":True}

@router.post("/feedback",status_code=201)
async def feedback(p:FeedbackCreate,user:User=Depends(get_current_user),db=Depends(get_db)):
    if SECRET.search(p.message):raise HTTPException(422,"Feedback must not contain credentials or tokens")
    row=UserFeedback(user_id=user.id,**p.model_dump());db.add(row);await db.flush();return {"id":row.id,"status":row.status,"created_at":row.created_at}

@router.get("/feedback")
async def own_feedback(user:User=Depends(get_current_user),db=Depends(get_db)):
    rows=(await db.scalars(select(UserFeedback).where(UserFeedback.user_id==user.id).order_by(UserFeedback.created_at.desc()).limit(100))).all();return [{"id":x.id,"category":x.category,"rating":x.rating,"message":x.message,"status":x.status,"created_at":x.created_at} for x in rows]

@router.get("/admin/analytics/summary")
async def analytics(days:int=Query(30,ge=1,le=90),_u:User=Depends(require_admin),db=Depends(get_db)):
    since=datetime.now(timezone.utc)-timedelta(days=days)
    events=(await db.execute(select(ProductEvent.event_name,func.count()).where(ProductEvent.created_at>=since).group_by(ProductEvent.event_name))).all();routes=(await db.execute(select(ProductEvent.route,func.count()).where(ProductEvent.created_at>=since).group_by(ProductEvent.route).order_by(func.count().desc()).limit(20))).all();feedback=(await db.execute(select(UserFeedback.status,func.count()).where(UserFeedback.created_at>=since).group_by(UserFeedback.status))).all();rating=await db.scalar(select(func.avg(UserFeedback.rating)).where(UserFeedback.created_at>=since))
    return {"days":days,"events":{k:int(v) for k,v in events},"top_routes":[{"route":k,"count":int(v)} for k,v in routes],"feedback":{k:int(v) for k,v in feedback},"average_rating":round(float(rating),2) if rating is not None else None}

@router.get("/admin/feedback")
async def feedback_queue(_u:User=Depends(require_admin),db=Depends(get_db)):
    rows=(await db.scalars(select(UserFeedback).order_by(UserFeedback.created_at.desc()).limit(200))).all();return [{"id":x.id,"category":x.category,"rating":x.rating,"message":x.message,"status":x.status,"created_at":x.created_at} for x in rows]

@router.patch("/admin/feedback/{fid}")
async def update_feedback(fid:str,p:FeedbackUpdate,_u:User=Depends(require_admin),db=Depends(get_db)):
    row=await db.get(UserFeedback,fid)
    if not row:raise HTTPException(404,"Feedback not found")
    row.status=p.status;return {"id":row.id,"status":row.status}

@router.post("/admin/releases",status_code=201)
async def create_release(p:ReleaseCreate,user:User=Depends(require_admin),db=Depends(get_db)):
    if await db.scalar(select(ReleaseRecord.id).where(ReleaseRecord.version==p.version)):raise HTTPException(409,"Release version already exists")
    row=ReleaseRecord(deployed_by=user.id,**p.model_dump());db.add(row);await db.flush();return {"id":row.id,"version":row.version,"status":row.status}

@router.get("/admin/releases")
async def releases(_u:User=Depends(require_admin),db=Depends(get_db)):
    rows=(await db.scalars(select(ReleaseRecord).order_by(ReleaseRecord.created_at.desc()).limit(100))).all();return [{"id":x.id,"version":x.version,"environment":x.environment,"status":x.status,"commit_sha":x.commit_sha,"notes":x.notes,"metrics":x.metrics,"created_at":x.created_at,"completed_at":x.completed_at} for x in rows]
