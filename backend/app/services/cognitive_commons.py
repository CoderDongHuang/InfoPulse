from collections import Counter
from fastapi import HTTPException
from app.services.trusted_ecosystem import digest,sign
def bft_consensus(nodes,votes,f):
 unique=set(nodes);required=2*f+1;valid=[v for v in votes if v.get("node") in unique and v.get("signature_valid")];counts=Counter(v.get("decision") for v in valid);decision,count=counts.most_common(1)[0] if counts else ("unknown",0);passed=len(unique)>=3*f+1 and count>=required;body={"nodes":sorted(unique),"decision":decision,"votes":sorted((v.get("node"),v.get("decision")) for v in valid),"f":f};return {"decision":decision,"conflicts":[v for v in valid if v.get("decision")!=decision],"consensus_hash":digest(body),"status":"committed" if passed else "failed"}
def constitution_compatibility(constitutions,permission,amendment):
 blocked=[]
 for c in constitutions:
  if permission not in c.get("permissions",[]):blocked.append(c.get("organization"))
  for k,v in c.get("entrenched",{}).items():
   if amendment.get(k,v)!=v:blocked.append(c.get("organization"))
 return {"compatibility":{"blocked_organizations":sorted(set(blocked)),"participants":len(constitutions)},"status":"compatible" if not blocked else "blocked"}
def preserve_evidence(previous,retired,new,witnesses):
 body={"previous":previous,"retired":retired,"new":new,"witnesses":sorted(set(witnesses))};valid=bool(previous.get("signature")) and len(set(witnesses))>=2
 return {"migration_proof":{**body,"signature":sign(body,"evidence-preservation")},"joint_verification":{"old_valid":bool(previous.get("signature")),"new_valid":valid},"status":"preserved" if valid else "blocked"}
def causal_validate(experiments,counterfactuals):
 regions={e.get("region") for e in experiments if e.get("replicated") and e.get("effect") is not None};effects={r:[e["effect"] for e in experiments if e.get("region")==r] for r in regions};regional={r:sum(v)/len(v) for r,v in effects.items()};aggregate=sum(regional.values())/len(regional) if regional else 0;consistent=not regional or max(regional.values())-min(regional.values())<=.25;body={"regional":regional,"aggregate":aggregate,"counterfactuals":counterfactuals};return {"regional_effects":regional,"aggregate_effect":round(aggregate,6),"proof":{**body,"signature":sign(body,"causal-signal")},"status":"validated" if len(regions)>=3 and consistent else "review"}
def settle_dissent(positions,pool):
 families={p.get("source_family") for p in positions};diversity=len(families)/max(len(positions),1);falsifiable=sum(1 for p in positions if p.get("falsifiable"))/len(positions);majority=Counter(p.get("position") for p in positions).most_common(1)[0][0];minority=[p for p in positions if p.get("position")!=majority and p.get("evidence_valid")];penalty=round(pool*(1-diversity)*.25);reward=(pool-penalty)//len(minority) if minority else 0;return {"source_diversity":round(diversity,4),"falsifiability_score":round(falsifiable,4),"minority_reward_cents":reward*len(minority),"convergence_penalty_cents":penalty,"settlement":{"minority_rewards":[{"participant":p.get("participant"),"cents":reward} for p in minority],"unallocated_cents":pool-reward*len(minority)-penalty,"balanced":reward*len(minority)+penalty<=pool}}
def reconcile_treasury(opening,revenues,grants,expenses,reserve):
 income=sum(x["cents"] for x in revenues);out=sum(x["cents"] for x in grants+expenses);closing=opening+income-out-reserve
 if closing<0:raise HTTPException(422,"Treasury is not balanced")
 return {"closing_cents":closing,"reconciliation":{"opening":opening,"income":income,"outflows":out,"reserve":reserve,"closing":closing,"balanced":opening+income==out+reserve+closing},"status":"balanced"}
def appeal_allocation(allocation,evidence,appellant,claimed,rate):
 proof_hash=digest(allocation.explanation_proof);original=next((x for x in allocation.allocations if x.get("requester")==appellant),{"amount":0});validated=all(e.get("verified") for e in evidence);difference=max(0,claimed-original.get("amount",0)) if validated else 0;comp=round(difference*rate);return {"original_proof_hash":proof_hash,"blind_evidence":[{k:v for k,v in e.items() if k not in {"author","organization"}} for e in evidence],"replay_result":{"original":original,"claimed":claimed,"difference":difference},"decision":{"upheld":difference>0},"compensation_cents":comp,"reputation_recovery":{"status":"scheduled" if difference>0 else "not_required"}}
def century_scenario(domains,years,interactions,interventions):
 path=[]
 for year in range(0,years+1,10):
  vals={k:v[min(year//10,len(v)-1)] if v else 0 for k,v in domains.items()};interaction=sum(i.get("weight",0)*vals.get(i.get("a"),0)*vals.get(i.get("b"),0) for i in interactions);path.append({"year":year,"domains":vals,"risk":round(min(1,sum(vals.values())/max(len(vals),1)+interaction),4)})
 return {"risk_path":path,"replay_hash":digest({"domains":domains,"years":years,"interactions":interactions,"interventions":interventions})}
def safety_valve_state(signatures,threshold,degraded,recovery,evidence):
 paused=len(set(signatures))>=threshold;drilled=evidence.get("offline_degraded") and evidence.get("controlled_recovery");state="active"
 if paused:state="degraded" if degraded and drilled else "paused"
 if paused and len(set(recovery))>=threshold and drilled:state="recovering"
 return {"state":state,"gate":{"pause_threshold_met":paused,"drill_passed":bool(drilled),"recovery_threshold_met":len(set(recovery))>=threshold}}
def federated_release_gate(build,mirrors,patch,attestations,compatibility):
 valid=build.status=="verified" and len({m.get("tier") for m in mirrors})>=2 and patch.get("signature_valid") and all(a.get("verified") for a in attestations) and all(compatibility.values());body={"build":build.artifact_digest,"mirrors":mirrors,"patch":patch,"attestations":attestations,"compatibility":compatibility};return {"release_proof":{**body,"signature":sign(body,"federated-release")},"status":"released" if valid else "blocked"}
