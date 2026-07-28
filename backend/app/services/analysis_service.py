from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.core.llm import complete_json, llm_is_configured
from app.models.intelligence import Analysis, AnalysisCitation, ContentItem, DataSource, EventContent

PROMPT_VERSION="analysis-v1"
async def evidence(db,event_ids,content_ids):
    ids=set(content_ids)
    if event_ids: ids.update((await db.scalars(select(EventContent.content_item_id).where(EventContent.event_id.in_(event_ids)))).all())
    if not ids: raise HTTPException(422,"没有选择任何可验证证据，拒绝生成结论")
    rows=(await db.execute(select(ContentItem,DataSource).join(DataSource).where(ContentItem.id.in_(ids),ContentItem.deleted_at.is_(None)).order_by(ContentItem.published_at.desc()).limit(50))).all()
    if not rows: raise HTTPException(422,"所选范围没有可访问的真实来源，拒绝生成结论")
    return rows

def fallback(kind,rows):
    claims=[]
    for i,(item,source) in enumerate(rows[:5]):
        text=(item.body or item.title).strip()[:260]
        claims.append({"claim":f"{item.title}：{text}","citation_indexes":[i],"inference":kind in {"forecast","impact","advice"},"uncertainty":"仅基于当前公开来源，后续信息可能改变判断" if kind=="forecast" else ""})
    return {"summary":f"基于 {len(rows)} 条真实来源形成的{kind}分析。","claims":claims}

async def create_analysis(db,user_id,payload,parent=None,instruction=""):
    rows=await evidence(db,payload.event_ids,payload.content_ids)
    model="evidence-rules-v1"
    result=fallback(payload.analysis_type,rows)
    if llm_is_configured():
        sources=[{"index":i,"title":x.title,"text":x.body[:1200],"url":x.canonical_url} for i,(x,_) in enumerate(rows)]
        result=await complete_json("只依据给定证据输出JSON。格式为summary和claims；每条claim必须有citation_indexes数组。预测必须inference=true并填写uncertainty。不得引用不存在的编号。",f"类型:{payload.analysis_type}\n补充:{instruction}\n证据:{sources}",temperature=.1,max_tokens=2500)
        model=get_settings().LLM_MODEL
    valid=[]
    for claim in result.get("claims",[]):
        indexes=[i for i in claim.get("citation_indexes",[]) if isinstance(i,int) and 0<=i<len(rows)]
        if indexes: claim["citation_indexes"]=indexes;valid.append(claim)
    if not valid: raise HTTPException(422,"分析没有形成可引用的事实结论，拒绝保存")
    result["claims"]=valid
    version=1 if not parent else parent.version+1
    item=Analysis(event_id=payload.event_ids[0] if len(payload.event_ids)==1 else None,user_id=user_id,parent_id=parent.id if parent else None,version=version,analysis_type=payload.analysis_type,status="completed",result=result,summary=result.get("summary",""),confidence=min(95,45+len(rows)*5),evidence_coverage=100,model_name=model,prompt_version=PROMPT_VERSION,data_from=min((x.published_at for x,_ in rows if x.published_at),default=None),data_to=max((x.published_at for x,_ in rows if x.published_at),default=None),generated_at=datetime.now(timezone.utc));db.add(item);await db.flush()
    for ci,claim in enumerate(valid):
        for idx in claim["citation_indexes"]:
            content,_=rows[idx];db.add(AnalysisCitation(analysis_id=item.id,content_item_id=content.id,quote=(content.body or content.title)[:500],locator={"url":content.canonical_url,"title":content.title},claim_index=ci))
    await db.flush();return item

async def serialize(db,item):
    cites=(await db.execute(select(AnalysisCitation,ContentItem,DataSource).join(ContentItem,ContentItem.id==AnalysisCitation.content_item_id).join(DataSource).where(AnalysisCitation.analysis_id==item.id).order_by(AnalysisCitation.claim_index))).all()
    return {"id":item.id,"event_id":item.event_id,"version":item.version,"analysis_type":item.analysis_type,"status":item.status,"result":item.result,"summary":item.summary,"confidence":item.confidence,"evidence_coverage":item.evidence_coverage,"model":{"name":item.model_name,"prompt_version":item.prompt_version},"data_scope":{"from":item.data_from,"to":item.data_to,"source_count":len({s.id for _,_,s in cites}),"citation_count":len(cites)},"generated_at":item.generated_at,"citations":[{"id":c.id,"claim_index":c.claim_index,"quote":c.quote,"content_id":x.id,"title":x.title,"source":s.name,"url":x.canonical_url,"published_at":x.published_at} for c,x,s in cites]}
