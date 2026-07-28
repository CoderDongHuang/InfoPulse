import re
from collections import Counter,defaultdict
from datetime import datetime,timezone
from sqlalchemy import delete,func,or_,select,update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.intelligence import AuditLog,ContentItem,DataSource,Entity,EntityAlias,EntityRelation,Event,EventContent,EventEntityLink,GraphQualitySnapshot,PropagationEdge,PropagationNode

KNOWN={"OpenAI":"company","DeepSeek":"company","Microsoft":"company","微软":"company","Google":"company","谷歌":"company","Meta":"company","Apple":"company","苹果":"company","GitHub":"product","ChatGPT":"product","Claude":"product","Gemini":"product","Cursor":"product","Java":"product","Python":"product","MCP":"project","Agent SDK":"product","人工智能":"industry","AI":"industry"}
SUFFIX=("公司","集团","大学","研究院","委员会","政府","项目","计划","政策","法案","条例")
def normalize(value:str)->str:return re.sub(r"[^\w\u4e00-\u9fff]","",value.casefold())
def candidates(text:str):
 found={}
 for name,kind in KNOWN.items():
  if re.search(rf"(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])",text,re.I):found[name]=kind
 for value in re.findall(r"[\u4e00-\u9fff]{2,16}(?:"+"|".join(SUFFIX)+r")",text):found[value]="policy" if value.endswith(("政策","法案","条例")) else "project" if value.endswith(("项目","计划")) else "organization"
 for value in re.findall(r"\b[A-Z][A-Za-z0-9.+-]{2,24}(?:\s+[A-Z][A-Za-z0-9.+-]{2,24}){0,2}\b",text):
  if value not in {"Official","The","This","Today"}:found.setdefault(value,"organization")
 return found
async def event_rows(db,event_id,max_nodes=200):return (await db.execute(select(ContentItem,DataSource).join(EventContent,EventContent.content_item_id==ContentItem.id).join(DataSource,DataSource.id==ContentItem.source_id).where(EventContent.event_id==event_id,ContentItem.deleted_at.is_(None)).order_by(ContentItem.published_at).limit(max_nodes))).all()
async def resolve_entity(db,name,kind):
 norm=normalize(name);entity=await db.scalar(select(Entity).outerjoin(EntityAlias,EntityAlias.entity_id==Entity.id).where(Entity.entity_type==kind,or_(Entity.normalized_name==norm,EntityAlias.normalized_alias==norm)))
 if entity:return entity
 entity=Entity(name=name,normalized_name=norm,entity_type=kind);db.add(entity);await db.flush();return entity
async def build_entities(db,event_id):
 rows=await event_rows(db,event_id);mentions=defaultdict(lambda:{"count":0,"ids":[],"name":"","kind":""})
 for content,_ in rows:
  for name,kind in candidates(f"{content.title}\n{content.body}").items():
   key=(normalize(name),kind);mentions[key]["count"]+=1;mentions[key]["ids"].append(content.id);mentions[key]["name"]=name;mentions[key]["kind"]=kind
 await db.execute(delete(EventEntityLink).where(EventEntityLink.event_id==event_id));entities=[]
 for item in mentions.values():
  entity=await resolve_entity(db,item["name"],item["kind"]);link=EventEntityLink(event_id=event_id,entity_id=entity.id,mention_count=item["count"],confidence=min(.98,.62+.08*item["count"]),evidence_content_ids=list(dict.fromkeys(item["ids"])));db.add(link);entities.append((entity,link))
 await db.flush();return entities
def influence(content):
 engagement=sum(x or 0 for x in (content.view_count,content.comment_count,content.like_count,content.share_count));return round(min(100,15+10*(engagement+1)**.25+(12 if content.is_official else 0)),2)
def explicit_reference(later,earlier):
 text=f"{later.title}\n{later.body}";raw=later.raw_payload or {};parent=str(raw.get("parent_id") or raw.get("referenced_id") or raw.get("source_url") or "")
 if earlier.canonical_url and earlier.canonical_url in text:
  position=text.find(earlier.canonical_url);return "reference",text[max(0,position-180):position+len(earlier.canonical_url)+180],earlier.canonical_url
 if earlier.external_id and earlier.external_id in parent:return "repost",parent,earlier.external_id
 title=earlier.title.strip()
 if len(title)>=16 and title.casefold() in text.casefold():return "reference",text[:800],title
 return None
async def build_propagation(db,event_id,max_nodes=80):
 rows=await event_rows(db,event_id,max_nodes);platforms={source.key for _,source in rows}
 await db.execute(delete(PropagationEdge).where(PropagationEdge.event_id==event_id));await db.execute(delete(PropagationNode).where(PropagationNode.event_id==event_id));await db.flush()
 nodes=[]
 for i,(content,source) in enumerate(rows):
  node=PropagationNode(event_id=event_id,content_item_id=content.id,platform=source.name,node_type="first_source" if i==0 else "official" if content.is_official else "media",occurred_at=content.published_at,influence_score=influence(content),is_verified=True);db.add(node);nodes.append((node,content,source))
 await db.flush();edges=[]
 if len(platforms)>=2:
  for j,(later_node,later,later_source) in enumerate(nodes):
   for earlier_node,earlier,earlier_source in nodes[:j]:
    if later_source.id==earlier_source.id:continue
    evidence=explicit_reference(later,earlier)
    if evidence:
     relation,quote,needle=evidence;edge=PropagationEdge(event_id=event_id,from_node_id=earlier_node.id,to_node_id=later_node.id,relation_type=relation,confidence=.96 if relation=="repost" else .9,evidence_content_id=later.id,evidence_quote=quote[:1000],created_by="system",is_verified=True);db.add(edge);edges.append(edge);break
 await db.flush();return nodes,edges,"ready" if edges else "insufficient_evidence"
async def similar_events(db,event_id,limit=8):
 current=set((await db.scalars(select(EventEntityLink.entity_id).where(EventEntityLink.event_id==event_id))).all());event=await db.get(Event,event_id);out=[]
 if not current:return out
 ids=(await db.scalars(select(EventEntityLink.event_id).where(EventEntityLink.entity_id.in_(current),EventEntityLink.event_id!=event_id).distinct())).all()
 for other_id in ids:
  other=await db.get(Event,other_id)
  if not other or other.deleted_at:continue
  theirs=set((await db.scalars(select(EventEntityLink.entity_id).where(EventEntityLink.event_id==other_id))).all());score=len(current&theirs)/len(current|theirs)
  if score:out.append({"id":other.id,"title":other.title,"category":other.category,"similarity":round(score,4),"shared_entity_count":len(current&theirs)})
 return sorted(out,key=lambda x:x["similarity"],reverse=True)[:limit]
async def quality(db,event_id):
 entity_links=(await db.scalars(select(EventEntityLink).where(EventEntityLink.event_id==event_id))).all();relations=(await db.scalars(select(EntityRelation).where(EntityRelation.event_id==event_id))).all();edges=(await db.scalars(select(PropagationEdge).where(PropagationEdge.event_id==event_id))).all();all_rel=list(relations)+list(edges);evidence=sum(bool(x.evidence_content_ids) if isinstance(x,EntityRelation) else bool(x.evidence_content_id and x.evidence_quote) for x in all_rel);verified=sum(x.is_verified for x in all_rel);precision=sum(x.confidence for x in entity_links)/len(entity_links) if entity_links else 0;snapshot=GraphQualitySnapshot(event_id=event_id,entity_precision=round(precision,4),evidence_coverage=round(evidence/len(all_rel),4) if all_rel else 0,verified_ratio=round(verified/len(all_rel),4) if all_rel else 0,unresolved_count=sum(x.confidence<.7 for x in entity_links),metrics={"entity_count":len(entity_links),"relation_count":len(relations),"propagation_edge_count":len(edges)});db.add(snapshot);await db.flush();return snapshot
async def audit(db,user_id,action,target_id,before,after):db.add(AuditLog(user_id=user_id,action=action,target_type="knowledge_graph",target_id=target_id,before_data=before,after_data=after))
