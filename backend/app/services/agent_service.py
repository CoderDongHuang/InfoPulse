import re
from sqlalchemy import or_,select
from app.config import get_settings
from app.core.llm import complete_json,llm_is_configured
from app.models.intelligence import ContentItem,DataSource,EventContent,Favorite
from app.services.knowledge import search as search_knowledge
async def gather(db,user_id,conversation,query,additions,knowledge_base_ids=None):
 ids=set();tools=[]
 if conversation.event_id: tools.append(("read_event",{"event_id":conversation.event_id}));ids.update((await db.scalars(select(EventContent.content_item_id).where(EventContent.event_id==conversation.event_id))).all())
 for x in additions:
  if x.get("type")=="content" and x.get("id"):ids.add(x["id"])
  if x.get("type")=="event" and x.get("id"):ids.update((await db.scalars(select(EventContent.content_item_id).where(EventContent.event_id==x["id"]))).all())
  if x.get("type")=="favorite":ids.update((await db.scalars(select(Favorite.target_id).where(Favorite.user_id==user_id,Favorite.target_type=="content"))).all())
 terms=[x for x in re.findall(r"[\w\u4e00-\u9fff]{2,}",query.lower()) if x not in {"今天","分析","总结","一下","什么","如何"}][:6]
 if terms:
  tools.append(("search",{"terms":terms}));condition=or_(*[ContentItem.title.ilike(f"%{x}%") for x in terms],*[ContentItem.body.ilike(f"%{x}%") for x in terms]);ids.update((await db.scalars(select(ContentItem.id).where(ContentItem.deleted_at.is_(None),condition).order_by(ContentItem.published_at.desc()).limit(20))).all())
 rows=(await db.execute(select(ContentItem,DataSource).join(DataSource).where(ContentItem.id.in_(ids),ContentItem.deleted_at.is_(None)).order_by(ContentItem.published_at.desc()).limit(30))).all() if ids else []
 private=await search_knowledge(db,user_id,knowledge_base_ids or [],query,10)
 if private:tools.append(("knowledge_base",{"knowledge_base_ids":knowledge_base_ids,"private_evidence_count":len(private)}))
 return list(rows)+[(x,None) for x in private],tools
async def answer(query,rows):
 def evidence_row(i,row):
  x,_=row
  if isinstance(x,dict):return {"index":i,"title":x["filename"],"text":x["quote"]}
  return {"index":i,"title":x.title,"text":x.body[:1000]}
 result={"answer":f"根据 {len(rows)} 条可访问来源，以下是与“{query}”相关的事实。","claims":[{"text":f"{evidence_row(i,row)['title']}：{evidence_row(i,row)['text'][:240]}","citation_indexes":[i]} for i,row in enumerate(rows[:5])]};model="evidence-rules-v1"
 if llm_is_configured():
  evidence=[evidence_row(i,row) for i,row in enumerate(rows)];result=await complete_json("只依据证据回答JSON：answer和claims；claims含text、citation_indexes，每条事实必须引用。",f"问题:{query}\n证据:{evidence}",temperature=.1,max_tokens=2200);model=get_settings().LLM_MODEL
 valid=[]
 for c in result.get("claims",[]):
  idx=[i for i in c.get("citation_indexes",[]) if isinstance(i,int) and 0<=i<len(rows)]
  if idx:c["citation_indexes"]=idx;valid.append(c)
 result["claims"]=valid
 if not valid:result={"answer":"当前上下文没有足够的可引用证据，无法给出事实性回答。","claims":[]}
 return result,model
