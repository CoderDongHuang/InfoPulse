from collections import deque
from fastapi import HTTPException
from app.services.trusted_ecosystem import digest,sign


def mesh_gate(proof_verified:bool,signatures:list[str],threshold:int,dependencies:list[dict])->dict:
 valid=proof_verified and len(set(signatures))>=threshold and all(d.get("status") not in {"revoked","blocked"} for d in dependencies)
 return {"valid":valid,"status":"available" if valid else "blocked"}
def hybrid_sign(subject:dict,classical_algorithm:str,pq_algorithm:str,historical:list[dict])->dict:
 classical=sign(subject,f"classical:{classical_algorithm}");pq=sign(subject,f"pq:{pq_algorithm}")
 return {"hybrid_signature":{"classical":classical,"post_quantum":pq,"algorithms":[classical_algorithm,pq_algorithm]},"historical_resignatures":[{"original":digest(p),"hybrid":sign(p,"pq-resign") } for p in historical]}
def verify_hybrid(subject:dict,signature:dict)->bool:
 algorithms=signature.get("algorithms",[])
 return len(algorithms)==2 and signature.get("classical")==sign(subject,f"classical:{algorithms[0]}") and signature.get("post_quantum")==sign(subject,f"pq:{algorithms[1]}")
def planetary_cascade(domains:list[str],topology:dict[str,list[str]],shocks:list[str])->dict:
 queue=deque((x,0) for x in shocks);seen=set();path=[]
 while queue:
  node,depth=queue.popleft()
  if node in seen:continue
  seen.add(node);domain=node.split(":",1)[0];path.append({"node":node,"domain":domain,"depth":depth})
  for target in topology.get(node,[]):queue.append((target,depth+1))
 touched={p["domain"] for p in path};score=round(len(touched)/max(len(set(domains)),1),4)
 return {"cascade_path":path,"recovery_plan":[f"restore:{x['node']}" for x in reversed(path)],"systemic_score":score,"replay_hash":digest({"domains":domains,"topology":topology,"shocks":shocks})}
def constitution_gate(constitution:dict,action:dict,vote:dict,veto:dict)->dict:
 violations=[]
 for key,value in constitution.get("forbidden",{}).items():
  if action.get(key)==value:violations.append({"rule":key,"reason":"constitution_forbidden"})
 quorum=vote.get("cast_weight",0)>=constitution.get("quorum_weight",1);approved=vote.get("yes_weight",0)>vote.get("no_weight",0)
 if not quorum:violations.append({"rule":"quorum"})
 if not approved:violations.append({"rule":"vote"})
 if veto.get("active"):violations.append({"rule":"human_veto","evidence":veto.get("evidence")})
 body={"constitution":digest(constitution),"action":digest(action),"vote":vote,"veto":veto,"violations":violations}
 return {"violations":violations,"execution_proof":{**body,"signature":sign(body,"agent-constitution")},"status":"allowed" if not violations else "blocked"}
def trade_amount(quantity:float,unit_price:int)->int:return round(quantity*unit_price)
def transition_trade(trade,listing,action:str,receipt:dict):
 allowed={"allocated":{"deliver","refund"},"delivered":{"settle","refund"}}
 if action not in allowed.get(trade.status,set()):raise HTTPException(409,"Invalid crisis trade transition")
 if action=="deliver":trade.status="delivered";trade.receipt={**receipt,"proof":digest(receipt)}
 elif action=="settle":trade.status="settled";trade.settlement={"seller_cents":trade.amount_cents,"buyer_debit_cents":trade.amount_cents,"balanced":True}
 else:trade.status="refunded";trade.settlement={"refund_cents":trade.amount_cents,"buyer_credit_cents":trade.amount_cents,"balanced":True};listing.capacity+=trade.quantity
 return trade
def insurance_terms(risks:dict[str,float],base_limit:int)->dict:
 score=min(1,max(risks.values(),default=0)*.7+(sum(risks.values())/max(len(risks),1))*.3);premium=round(base_limit*(.01+.09*score));reserve=round(base_limit*(.2+.5*score))
 return {"premium_cents":premium,"coverage_limit_cents":base_limit,"reserve_cents":reserve,"risk_score":round(score,4)}
def insurance_claim(policy,event:dict,loss:int)->dict:
 triggered=all(event.get(k)==v for k,v in policy.trigger.items());payout=min(loss,policy.coverage_limit_cents,policy.reserve_cents) if triggered else 0
 return {"triggered":triggered,"loss_cents":loss,"payout_cents":payout,"remaining_reserve_cents":policy.reserve_cents-payout,"balanced":payout+(policy.reserve_cents-payout)==policy.reserve_cents}
def memory_transfer_gate(memory,purpose:str,source:str,target:str,retention)->dict:
 valid=purpose in memory.allowed_purposes and source==target and retention<=memory.expires_at and memory.status in {"active","quarantined"}
 target_body={"memory":memory.memory_key,"hash":memory.content_hash,"purpose":purpose,"region":target,"retention":str(retention)}
 erasure_body={"memory":memory.memory_key,"source":source,"previous_hash":memory.content_hash,"erased":True}
 return {"target_inclusion_proof":{**target_body,"signature":sign(target_body,"memory-inclusion")},"source_erasure_proof":{**erasure_body,"signature":sign(erasure_body,"memory-erasure")},"status":"completed" if valid else "blocked"}
def append_edge_message(previous,node_id:int|str,sequence:int,clock:dict,payload:dict)->dict:
 previous_hash=previous.chain_hash if previous else "";payload_hash=digest(payload);body={"previous":previous_hash,"node":node_id,"sequence":sequence,"clock":clock,"payload":payload_hash}
 return {"payload_hash":payload_hash,"signature":sign(body,"edge-message"),"previous_hash":previous_hash,"chain_hash":digest({**body,"signature":sign(body,"edge-message")})}
def converge_edge(messages:list)->dict:
 ordered=sorted(messages,key=lambda x:(sum(x.vector_clock.values()),x.node_id,x.sequence,x.chain_hash));clock={}
 for msg in ordered:
  for node,value in msg.vector_clock.items():clock[node]=max(clock.get(node,0),value)
 return {"message_ids":[m.id for m in ordered],"vector_clock":clock,"convergence_hash":digest([m.chain_hash for m in ordered])}
def public_commitment(metrics:dict,fairness:dict,externalities:dict,allocation:dict,observers:list[str])->dict:
 body={"metrics":metrics,"fairness":fairness,"externalities":externalities,"resource_allocation":allocation}
 return {"public_commitment":digest(body),"observer_proofs":[sign({"commitment":digest(body),"observer":o},"public-interest") for o in sorted(set(observers))]}
