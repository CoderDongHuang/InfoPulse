"""Evidence-first multilingual intelligence and decision-support helpers."""
import json,re
from sqlalchemy import select
from openai import AsyncOpenAI
from app.config import get_settings
from app.models.global_intelligence import ContentTranslation,GlobalNarrative,NarrativeSignal,Scenario,DecisionAudit,DecisionOption
from app.models.intelligence import ContentItem,EventContent,EventEntityLink
settings=get_settings()
def language_of(text:str):
 if re.search(r"[\u4e00-\u9fff]",text):return "zh"
 if re.search(r"[\u0400-\u04ff]",text):return "ru"
 if re.search(r"[\u0600-\u06ff]",text):return "ar"
 if re.search(r"[\u3040-\u30ff]",text):return "ja"
 return "en" if re.search(r"[A-Za-z]",text) else "und"
def model_client():
 if not settings.LLM_API_KEY:raise RuntimeError("Approved translation/model credential is not configured")
 return AsyncOpenAI(api_key=settings.LLM_API_KEY,base_url=settings.LLM_API_BASE)
async def translate(db,org_id,user_id,content,target):
 source=content.language if content.language and content.language!="und" else language_of(content.title+content.body)
 old=await db.scalar(select(ContentTranslation).where(ContentTranslation.content_item_id==content.id,ContentTranslation.target_language==target))
 if old:return old
 prompt=f"Translate faithfully from {source} to {target}. Preserve names, dates, uncertainty and URLs. Return strict JSON {{title,body}}. Do not add facts.\nTITLE:\n{content.title}\nBODY:\n{content.body[:12000]}"
 response=await model_client().chat.completions.create(model=settings.LLM_MODEL,messages=[{"role":"user","content":prompt}],temperature=0,response_format={"type":"json_object"})
 data=json.loads(response.choices[0].message.content or "{}")
 if not str(data.get("title","")).strip():raise RuntimeError("Translation model returned no translated title")
 row=ContentTranslation(organization_id=org_id,content_item_id=content.id,source_language=source,target_language=target,translated_title=str(data["title"]).strip(),translated_body=str(data.get("body","")).strip(),model_name=settings.LLM_MODEL,quality_score=0,status="ready",created_by=user_id);db.add(row);await db.flush();return row
async def event_content(db,event_id):return (await db.scalars(select(ContentItem).join(EventContent,EventContent.content_item_id==ContentItem.id).where(EventContent.event_id==event_id,ContentItem.deleted_at.is_(None)))).all()
async def build_narratives(db,org_id,event_id,workspace_id=None):
 rows=await event_content(db,event_id);groups={}
 for c in rows:
  entities=tuple(sorted(str(x).casefold() for x in c.entities[:8])) or tuple(re.findall(r"[A-Za-z]{4,}",c.title.casefold())[:3])
  if not entities:continue
  key="|".join(entities);g=groups.setdefault(key,[]);g.append(c)
 created=[]
 for key,items in groups.items():
  langs=sorted({x.language if x.language!="und" else language_of(x.title+x.body) for x in items});
  if len(langs)<2:continue
  regions=sorted({x.region for x in items if x.region});ids=[x.id for x in items];row=GlobalNarrative(organization_id=org_id,workspace_id=workspace_id,event_id=event_id,title=items[0].title,normalized_key=key,languages=langs,regions=regions,content_item_ids=ids,confidence=round(min(.95,.5+.1*len(langs)+.03*len(items)),2));db.add(row);await db.flush();created.append(row)
  text="\n".join(f"{x.title}\n{x.body}" for x in items).casefold();markers=[("coordination",["copy this","转发","share this","everyone post"]),("unverified_claim",["rumor","unconfirmed","据传","网传"]),("manipulative_framing",["traitor","敌人","must act","必须"])]
  for kind,terms in markers:
   if any(t in text for t in terms):db.add(NarrativeSignal(organization_id=org_id,narrative_id=row.id,signal_type=kind,severity="review",confidence=.55,evidence_content_ids=ids,explanation="Rule-based signal requires analyst review; it is not a finding of coordinated manipulation."))
 return created
async def scenario(db,org_id,user_id,payload):
 valid=set((await db.scalars(select(ContentItem.id).join(EventContent,EventContent.content_item_id==ContentItem.id).where(EventContent.event_id==payload.event_id,ContentItem.id.in_(payload.evidence_content_ids),ContentItem.deleted_at.is_(None)))).all())
 if len(valid)<2:raise ValueError("A scenario requires at least two accessible event sources")
 rows=(await db.scalars(select(ContentItem).where(ContentItem.id.in_(valid)))).all();langs={x.language for x in rows};regions={x.region for x in rows if x.region};gaps=[]
 if len(langs)<2:gaps.append("No cross-language corroboration")
 if not regions:gaps.append("No regional metadata")
 chain=[{"step":1,"claim":"Observed source evidence","content_ids":sorted(valid)},{"step":2,"claim":"Assumption under review","assumptions":payload.assumptions},{"step":3,"claim":"Potential impact requires monitoring","status":"not_a_prediction"}]
 row=Scenario(organization_id=org_id,workspace_id=payload.workspace_id,event_id=payload.event_id,name=payload.name,assumptions=payload.assumptions,impact_chain=chain,risk_score=.5,confidence=round(.55+.05*min(len(valid),5),2),evidence_content_ids=sorted(valid),evidence_gaps=gaps,status="evidence_ready",created_by=user_id);db.add(row);await db.flush();return row
def audit(db,org,room,user,action,details):db.add(DecisionAudit(organization_id=org,room_id=room,actor_id=user,action=action,details=details))
async def red_team(db,option):
 rows=(await db.scalars(select(ContentItem).where(ContentItem.id.in_(option.evidence_content_ids)))).all();gaps=[]
 if len(rows)<2:gaps.append("Only one source supports this option")
 if len({x.language for x in rows})<2:gaps.append("No cross-language corroboration")
 return ["What evidence would falsify the expected benefit?","Which affected group is absent from the cited sources?","What reversible step can be taken first?"],gaps
