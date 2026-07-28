import asyncio,json
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.intelligence import AgentMessage,Conversation,MessageCitation,MessageFeedback,ContentItem,DataSource
from app.schemas.agent import ConversationCreate,ConversationUpdate,FeedbackCreate,MessageCreate
from app.services.agent_service import answer,gather
router=APIRouter(prefix="/api/v1/conversations",tags=["AI Agent"])
def emit(e,d):return f"event: {e}\ndata: {json.dumps(d,ensure_ascii=False,default=str)}\n\n"
async def owned(db,cid,uid):
 c=await db.scalar(select(Conversation).where(Conversation.id==cid,Conversation.user_id==uid,Conversation.deleted_at.is_(None)))
 if not c:raise HTTPException(404,"会话不存在")
 return c
async def message_dict(db,m):
 cites=(await db.execute(select(MessageCitation,ContentItem,DataSource).join(ContentItem,ContentItem.id==MessageCitation.content_item_id).join(DataSource).where(MessageCitation.message_id==m.id))).all()
 return {"id":m.id,"role":m.role,"content":m.content,"status":m.status,"tool_name":m.tool_name,"tool_payload":m.tool_payload,"model_name":m.model_name,"created_at":m.created_at,"citations":[{"id":c.id,"quote":c.quote,"title":x.title,"source":s.name,"url":x.canonical_url} for c,x,s in cites]}
@router.get("")
async def listing(user:User=Depends(get_current_user),db=Depends(get_db)):return [{"id":x.id,"title":x.title,"event_id":x.event_id,"updated_at":x.updated_at} for x in (await db.scalars(select(Conversation).where(Conversation.user_id==user.id,Conversation.deleted_at.is_(None)).order_by(Conversation.updated_at.desc()))).all()]
@router.post("",status_code=201)
async def create(p:ConversationCreate,user:User=Depends(get_current_user),db=Depends(get_db)):
 c=Conversation(user_id=user.id,title=p.title,event_id=p.event_id,context_config=p.context_config);db.add(c);await db.flush();return {"id":c.id,"title":c.title,"event_id":c.event_id,"context_config":c.context_config}
@router.get("/{cid}")
async def detail(cid:str,user:User=Depends(get_current_user),db=Depends(get_db)):
 c=await owned(db,cid,user.id);msgs=(await db.scalars(select(AgentMessage).where(AgentMessage.conversation_id==cid).order_by(AgentMessage.created_at))).all();return {"id":c.id,"title":c.title,"event_id":c.event_id,"context_config":c.context_config,"messages":[await message_dict(db,x) for x in msgs]}
@router.patch("/{cid}")
async def update(cid:str,p:ConversationUpdate,user:User=Depends(get_current_user),db=Depends(get_db)):
 c=await owned(db,cid,user.id)
 for k,v in p.model_dump(exclude_none=True).items():setattr(c,k,v)
 return {"id":c.id,"title":c.title,"context_config":c.context_config}
@router.delete("/{cid}",status_code=204)
async def remove(cid:str,user:User=Depends(get_current_user),db=Depends(get_db)):(await owned(db,cid,user.id)).deleted_at=datetime.now(timezone.utc)
@router.post("/{cid}/messages")
async def send(cid:str,p:MessageCreate,request:Request,user:User=Depends(get_current_user),db=Depends(get_db)):
 c=await owned(db,cid,user.id);u=AgentMessage(conversation_id=cid,role="user",content=p.content,status="completed");a=AgentMessage(conversation_id=cid,role="assistant",status="streaming");db.add_all([u,a]);c.updated_at=datetime.now(timezone.utc);await db.commit()
 async def stream():
  yield emit("message.started",{"message_id":a.id})
  try:
   rows,tools=await gather(db,user.id,c,p.content,p.context_additions)
   for name,payload in tools:yield emit("tool.started",{"name":name,"payload":payload});yield emit("tool.completed",{"name":name,"count":len(rows)})
   if p.knowledge_base_ids:yield emit("tool.completed",{"name":"knowledge_base","status":"unavailable","message":"知识库尚未启用，未使用私有文档"})
   result,model=await answer(p.content,rows);text=result["answer"]+("\n" if result["claims"] else "")+"\n".join(x["text"] for x in result["claims"])
   for part in [text[i:i+24] for i in range(0,len(text),24)]:
    if await request.is_disconnected():a.status="cancelled";await db.commit();return
    yield emit("message.delta",{"text":part});await asyncio.sleep(0)
   a.content=text;a.model_name=model;a.status="completed";used=set()
   for ci,claim in enumerate(result["claims"]):
    for idx in claim["citation_indexes"]:
     if idx in used:continue
     used.add(idx);x,_=rows[idx];mc=MessageCitation(message_id=a.id,content_item_id=x.id,quote=(x.body or x.title)[:500],locator={"url":x.canonical_url},claim_index=ci);db.add(mc);await db.flush();yield emit("citation.added",{"id":mc.id,"title":x.title,"url":x.canonical_url})
   await db.commit();yield emit("message.completed",await message_dict(db,a))
  except asyncio.CancelledError:a.status="cancelled";await db.commit();raise
  except Exception:a.status="failed";await db.commit();yield emit("message.failed",{"message":"Agent 执行失败，未保存为完成回答"})
 return StreamingResponse(stream(),media_type="text/event-stream",headers={"X-Accel-Buffering":"no","Cache-Control":"no-cache"})
@router.post("/{cid}/messages/{mid}/feedback")
async def feedback(cid:str,mid:str,p:FeedbackCreate,user:User=Depends(get_current_user),db=Depends(get_db)):
 await owned(db,cid,user.id);m=await db.scalar(select(AgentMessage).where(AgentMessage.id==mid,AgentMessage.conversation_id==cid,AgentMessage.role=="assistant"))
 if not m:raise HTTPException(404,"消息不存在")
 f=await db.scalar(select(MessageFeedback).where(MessageFeedback.message_id==mid,MessageFeedback.user_id==user.id))
 if f:f.rating=p.rating;f.reason=p.reason
 else:db.add(MessageFeedback(message_id=mid,user_id=user.id,**p.model_dump()))
 return {"message_id":mid,"rating":p.rating}
