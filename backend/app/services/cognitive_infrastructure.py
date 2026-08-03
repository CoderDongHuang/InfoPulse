from collections import Counter
from app.services.trusted_ecosystem import digest,sign


def certify_proofs(implementations:list[dict],vectors:list[dict],revocations:list[dict])->dict:
 names={x.get("name") for x in implementations};formats={x.get("format") for x in implementations};all_vectors=all(all(impl.get("results",{}).get(v.get("id")) is True for v in vectors) for impl in implementations);revoked=all(x.get("rejected") is True for x in revocations) if revocations else False;passed=len(names)>=3 and len(formats)==1 and all_vectors and revoked
 body={"implementations":sorted(names),"format":next(iter(formats),""),"vectors":[v.get("id") for v in vectors],"revocation":revoked,"passed":passed}
 return {"results":body,"revocation_result":{"passed":revoked},"certificate_hash":digest(body),"status":"certified" if passed else "failed"}
def constitution_upgrade_gate(current:dict,proposed:dict,impact:dict,vote:dict,effective_at,rollback:dict)->dict:
 entrenched=current.get("entrenched",{});weakened=[k for k,v in entrenched.items() if proposed.get(k)!=v];passed=impact.get("tested") is True and not impact.get("critical_regressions") and vote.get("yes_weight",0)>vote.get("no_weight",0) and vote.get("cast_weight",0)>=vote.get("quorum_weight",1) and bool(rollback.get("tested")) and not weakened
 return {"status":"scheduled" if passed else "blocked","gate":{"weakened_entrenched":weakened,"impact_passed":impact.get("tested") is True,"vote_passed":vote.get("yes_weight",0)>vote.get("no_weight",0),"delayed_effective":str(effective_at),"rollback_tested":bool(rollback.get("tested"))}}
def append_archive(previous,p,sequence:int)->dict:
 previous_root=previous.archive_root if previous else "";body={"sequence":sequence,"object":p.object_id,"content":p.content_hash,"algorithm":p.algorithm,"previous":previous_root};root=sign(body,"pq-archive");resign=[{"root":r,"algorithm":p.algorithm,"signature":sign({"root":r,"algorithm":p.algorithm},"archive-resign")} for r in p.historical_roots]
 return {"previous_root":previous_root,"archive_root":root,"resignatures":resign}
def signal_quality(sources:list[dict],metric:dict,purposes:list[str])->dict:
 families={s.get("family") for s in sources};owners={s.get("owner") for s in sources};diversity=min(1,(len(families)+len(owners))/(2*max(len(sources),1)));valid=diversity>=.5 and bool(purposes)
 return {"source_diversity":round(diversity,4),"commitment":digest({"metric":metric,"sources":sorted(str(s.get("proof")) for s in sources),"purposes":purposes}),"status":"published" if valid else "review"}
def epistemic_risk(graph:dict[str,list[str]],families:dict[str,str],outputs:list[dict],narratives:dict)->dict:
 findings=[]
 def cycle(node,path):
  if node in path:return True
  return any(cycle(n,path|{node}) for n in graph.get(node,[]))
 if any(cycle(n,set()) for n in graph):findings.append("evidence_cycle")
 counts=Counter(families.values());concentration=max(counts.values(),default=0)/max(sum(counts.values()),1)
 if concentration>.6:findings.append("source_homogeneity")
 answers=Counter(str(x.get("answer")) for x in outputs);consensus=max(answers.values(),default=0)/max(len(outputs),1)
 independent=len({x.get("evidence_root") for x in outputs})/max(len(outputs),1)
 if consensus>.8 and independent<.5:findings.append("consensus_hallucination")
 if narratives.get("manipulation_score",0)>=.7:findings.append("narrative_manipulation")
 score=min(1,len(findings)*.25+concentration*.2);return {"findings":findings,"risk_score":round(score,4),"gate_status":"blocked" if findings else "allowed"}
def clear_assets(assets:dict[str,int],obligations:list[dict],prices:dict[str,float],buffers:dict[str,int],shock:float)->dict:
 net={party:{} for party in {x["from"] for x in obligations}|{x["to"] for x in obligations}}
 for item in obligations:
  asset=item["asset"];amount=item["amount"];net[item["from"]][asset]=net[item["from"]].get(asset,0)-amount;net[item["to"]][asset]=net[item["to"]].get(asset,0)+amount
 conserved=all(sum(p.get(asset,0) for p in net.values())==0 for asset in assets);required=sum(max(0,-sum(amount*prices.get(asset,0)*(1-shock) for asset,amount in position.items())) for position in net.values());available=sum(v*prices.get(k,1) for k,v in buffers.items());tripped=not conserved or required>available
 return {"net_positions":net,"stress_result":{"required_buffer":round(required),"available_buffer":round(available),"conserved":conserved},"circuit_state":"open" if tripped else "closed","status":"blocked" if tripped else "settled"}
def fair_allocate(capacity:float,requests:list[dict])->dict:
 scored=[]
 for r in requests:
  score=r.get("urgency",0)*.35+r.get("vulnerability",0)*.3+r.get("public_interest",0)*.25+(1-r.get("historical_share",0))*.1;scored.append((score,r))
 total=sum(max(s,0) for s,_ in scored);alloc=[];remaining=capacity
 for index,(score,r) in enumerate(sorted(scored,key=lambda x:(-x[0],x[1].get("requester","")))):
  amount=min(r.get("requested",0),remaining if index==len(scored)-1 else capacity*score/total if total else 0);remaining-=amount;alloc.append({"requester":r.get("requester"),"amount":round(amount,4),"score":round(score,4),"factors":{k:r.get(k,0) for k in ("urgency","vulnerability","public_interest","historical_share")}})
 body={"capacity":capacity,"allocations":alloc};return {"allocations":alloc,"fairness_metrics":{"allocated":round(capacity-remaining,4),"unallocated":round(remaining,4)},"explanation_proof":{**body,"signature":sign(body,"fair-allocation")}}
def long_horizon(drivers:dict[str,list[float]],years:int,interventions:list[dict])->dict:
 path=[]
 for year in range(years+1):
  values={k:v[min(year,len(v)-1)] if v else 0 for k,v in drivers.items()};risk=min(1,sum(values.values())/max(len(values),1));path.append({"year":year,"drivers":values,"risk":round(risk,4)})
 milestones=[x for x in path if x["year"]%5==0];return {"milestones":milestones,"risk_path":path,"replay_hash":digest({"drivers":drivers,"years":years,"interventions":interventions})}
def commitment_audit(baseline:dict,current:dict,costs:dict,externalities:dict,beneficiaries:list[str])->dict:
 progress={k:current.get(k,0)-v for k,v in baseline.items()};future_cost=sum(costs.get(x,0) for x in beneficiaries);external=sum(externalities.values());passed=all(v>=0 for v in progress.values()) and future_cost+external<=0
 return {"progress":progress,"future_cost_transfer":future_cost,"externality_total":external,"beneficiaries":beneficiaries,"passed":passed,"commitment":digest({"progress":progress,"costs":costs,"externalities":externalities})}
def build_gate(source:str,artifact:str,reproduction:str,hardware:dict,capabilities:list[str])->str:
 required={"identity","policy","audit","upgrade"};return "verified" if artifact==reproduction and hardware.get("verified") is True and required<=set(capabilities) else "blocked"
def upgrade_gate(build_status:str,signature:bool,offline:dict,rollback:dict)->str:return "ready" if build_status=="verified" and signature and offline.get("passed") is True and rollback.get("verified") is True else "blocked"
