from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import delete,select,update
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.intelligence import AuditLog,ContentItem,DataSource,Entity,EntityAlias,EntityRelation,EventContent,EventEntityLink,PropagationEdge,PropagationNode
from app.schemas.graph import EdgeCorrection,EntityCorrection,EntityMerge,GraphBuildRequest,RelationCreate
from app.services.event_service import get_event_or_error
from app.services.knowledge_graph import audit,build_entities,build_propagation,normalize,quality,resolve_entity,similar_events
router=APIRouter(prefix="/api/v1/events",tags=["Knowledge Graph"])
async def graph_data(db,event_id,max_nodes=100):
 links=(await db.execute(select(EventEntityLink,Entity).join(Entity,Entity.id==EventEntityLink.entity_id).where(EventEntityLink.event_id==event_id).order_by(EventEntityLink.mention_count.desc()).limit(max_nodes))).all();relations=(await db.scalars(select(EntityRelation).where(EntityRelation.event_id==event_id).limit(max_nodes*2))).all();return {"nodes":[{"id":e.id,"name":e.name,"normalized_name":e.normalized_name,"entity_type":e.entity_type,"role":l.role,"mention_count":l.mention_count,"confidence":l.confidence,"evidence_content_ids":l.evidence_content_ids} for l,e in links],"edges":[{"id":r.id,"from":r.from_entity_id,"to":r.to_entity_id,"relation_type":r.relation_type,"confidence":r.confidence,"evidence_content_ids":r.evidence_content_ids,"created_by":r.created_by,"is_verified":r.is_verified} for r in relations],"limited":len(links)>=max_nodes}
@router.post("/{event_id}/graph/build")
async def build_graph(event_id:str,p:GraphBuildRequest,user:User=Depends(get_current_user),db=Depends(get_db)):await get_event_or_error(db,event_id);entities=await build_entities(db,event_id);await audit(db,user.id,"graph.build",event_id,{}, {"entity_count":len(entities)});return await graph_data(db,event_id,p.max_nodes)
@router.get("/{event_id}/graph")
async def get_graph(event_id:str,max_nodes:int=Query(100,ge=2,le=200),_u:User=Depends(get_current_user),db=Depends(get_db)):await get_event_or_error(db,event_id);return await graph_data(db,event_id,max_nodes)
@router.get("/{event_id}/similar")
async def get_similar(event_id:str,_u:User=Depends(get_current_user),db=Depends(get_db)):await get_event_or_error(db,event_id);return {"items":await similar_events(db,event_id)}
@router.post("/{event_id}/propagation/build")
async def propagation_build(event_id:str,p:GraphBuildRequest,user:User=Depends(get_current_user),db=Depends(get_db)):await get_event_or_error(db,event_id);nodes,edges,status=await build_propagation(db,event_id,p.max_nodes);await audit(db,user.id,"propagation.build",event_id,{}, {"node_count":len(nodes),"edge_count":len(edges),"status":status});return await propagation_data(db,event_id,status)
async def propagation_data(db,event_id,status=None):
 rows=(await db.execute(select(PropagationNode,ContentItem,DataSource).join(ContentItem,ContentItem.id==PropagationNode.content_item_id).join(DataSource,DataSource.id==ContentItem.source_id).where(PropagationNode.event_id==event_id).order_by(PropagationNode.occurred_at))).all();edges=(await db.scalars(select(PropagationEdge).where(PropagationEdge.event_id==event_id))).all();platforms={x.platform for x,_,_ in rows};status=status or ("ready" if edges else "insufficient_evidence");return {"status":status,"reason":"至少需要两个平台且后续内容必须明确引用前序内容" if status!="ready" else "","nodes":[{"id":n.id,"content_id":c.id,"title":c.title,"url":c.canonical_url,"platform":n.platform,"node_type":n.node_type,"occurred_at":n.occurred_at,"influence_score":n.influence_score,"is_verified":n.is_verified} for n,c,s in rows],"edges":[{"id":e.id,"from":e.from_node_id,"to":e.to_node_id,"relation_type":e.relation_type,"confidence":e.confidence,"evidence_content_id":e.evidence_content_id,"evidence_quote":e.evidence_quote,"created_by":e.created_by,"is_verified":e.is_verified} for e in edges],"platform_count":len(platforms)}
@router.get("/{event_id}/propagation")
async def propagation_get(event_id:str,_u:User=Depends(get_current_user),db=Depends(get_db)):await get_event_or_error(db,event_id);return await propagation_data(db,event_id)
@router.post("/{event_id}/entities")
async def correct_entity(event_id:str,p:EntityCorrection,user:User=Depends(get_current_user),db=Depends(get_db)):
 await get_event_or_error(db,event_id);entity=await resolve_entity(db,p.name,p.entity_type)
 for alias in p.aliases:
  norm=normalize(alias)
  if norm and not await db.scalar(select(EntityAlias).where(EntityAlias.entity_id==entity.id,EntityAlias.normalized_alias==norm)):db.add(EntityAlias(entity_id=entity.id,alias=alias,normalized_alias=norm,language="zh" if any('\u4e00'<=c<='\u9fff' for c in alias) else "en"))
 link=await db.scalar(select(EventEntityLink).where(EventEntityLink.event_id==event_id,EventEntityLink.entity_id==entity.id,EventEntityLink.role==p.role))
 if link:link.evidence_content_ids=list(dict.fromkeys(link.evidence_content_ids+p.evidence_content_ids));link.confidence=1
 else:db.add(EventEntityLink(event_id=event_id,entity_id=entity.id,role=p.role,mention_count=1,confidence=1,evidence_content_ids=p.evidence_content_ids))
 await audit(db,user.id,"graph.entity.correct",event_id,{},p.model_dump());return {"id":entity.id,"name":entity.name,"entity_type":entity.entity_type}
@router.post("/{event_id}/entities/merge")
async def merge_entity(event_id:str,p:EntityMerge,user:User=Depends(get_current_user),db=Depends(get_db)):
 await get_event_or_error(db,event_id);source=await db.get(Entity,p.source_entity_id);target=await db.get(Entity,p.target_entity_id)
 if not source or not target or source.id==target.id:raise HTTPException(422,"实体合并参数无效")
 linked=set((await db.scalars(select(EventEntityLink.entity_id).where(EventEntityLink.event_id==event_id,EventEntityLink.entity_id.in_([source.id,target.id])))).all())
 if linked!={source.id,target.id}:raise HTTPException(422,"仅允许合并当前事件中的实体")
 source_links=(await db.scalars(select(EventEntityLink).where(EventEntityLink.entity_id==source.id))).all()
 for link in source_links:
  existing=await db.scalar(select(EventEntityLink).where(EventEntityLink.event_id==link.event_id,EventEntityLink.entity_id==target.id,EventEntityLink.role==link.role))
  if existing:existing.mention_count+=link.mention_count;existing.evidence_content_ids=list(dict.fromkeys(existing.evidence_content_ids+link.evidence_content_ids));await db.delete(link)
  else:link.entity_id=target.id
 await db.execute(update(EntityRelation).where(EntityRelation.from_entity_id==source.id).values(from_entity_id=target.id));await db.execute(update(EntityRelation).where(EntityRelation.to_entity_id==source.id).values(to_entity_id=target.id));db.add(EntityAlias(entity_id=target.id,alias=source.name,normalized_alias=source.normalized_name));await db.delete(source);await audit(db,user.id,"graph.entity.merge",event_id,{"source":p.source_entity_id},{"target":p.target_entity_id});return {"merged":True}
@router.post("/{event_id}/relations")
async def create_relation(event_id:str,p:RelationCreate,user:User=Depends(get_current_user),db=Depends(get_db)):
 await get_event_or_error(db,event_id);linked=set((await db.scalars(select(EventEntityLink.entity_id).where(EventEntityLink.event_id==event_id,EventEntityLink.entity_id.in_([p.from_entity_id,p.to_entity_id])))).all())
 if linked!={p.from_entity_id,p.to_entity_id}:raise HTTPException(422,"关系两端必须属于当前事件")
 valid=set((await db.scalars(select(ContentItem.id).join(EventContent,EventContent.content_item_id==ContentItem.id).where(EventContent.event_id==event_id,ContentItem.id.in_(p.evidence_content_ids)))).all())
 if len(valid)!=len(set(p.evidence_content_ids)):raise HTTPException(422,"关系证据必须属于当前事件")
 relation=EntityRelation(event_id=event_id,from_entity_id=p.from_entity_id,to_entity_id=p.to_entity_id,relation_type=p.relation_type,confidence=p.confidence,evidence_content_ids=list(valid),created_by="user",is_verified=True);db.add(relation);await db.flush();await audit(db,user.id,"graph.relation.create",event_id,{},p.model_dump());return {"id":relation.id}
@router.patch("/{event_id}/propagation/edges/{edge_id}")
async def correct_edge(event_id:str,edge_id:str,p:EdgeCorrection,user:User=Depends(get_current_user),db=Depends(get_db)):
 edge=await db.scalar(select(PropagationEdge).where(PropagationEdge.id==edge_id,PropagationEdge.event_id==event_id))
 if not edge:raise HTTPException(404,"传播关系不存在")
 before={"relation_type":edge.relation_type,"confidence":edge.confidence,"is_verified":edge.is_verified}
 for k,v in p.model_dump(exclude_none=True).items():setattr(edge,k,v)
 edge.created_by="user";await audit(db,user.id,"propagation.edge.correct",event_id,before,p.model_dump(exclude_none=True));return {"id":edge.id,"relation_type":edge.relation_type,"confidence":edge.confidence,"is_verified":edge.is_verified}
@router.get("/{event_id}/graph/quality")
async def graph_quality(event_id:str,_u:User=Depends(get_current_user),db=Depends(get_db)):
 await get_event_or_error(db,event_id);x=await quality(db,event_id);return {"entity_precision":x.entity_precision,"evidence_coverage":x.evidence_coverage,"verified_ratio":x.verified_ratio,"unresolved_count":x.unresolved_count,"metrics":x.metrics,"created_at":x.created_at}
@router.get("/{event_id}/graph/audit-logs")
async def graph_audits(event_id:str,_u:User=Depends(get_current_user),db=Depends(get_db)):return [{"id":x.id,"action":x.action,"before":x.before_data,"after":x.after_data,"created_at":x.created_at} for x in (await db.scalars(select(AuditLog).where(AuditLog.target_type=="knowledge_graph",AuditLog.target_id==event_id).order_by(AuditLog.created_at.desc()))).all()]
