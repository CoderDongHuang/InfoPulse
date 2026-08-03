import unittest
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from app.services.cognitive_infrastructure import *
class CognitiveInfrastructureTests(unittest.TestCase):
 def test_three_implementations_certify_vectors_and_revocation(self):
  implementations=[{"name":n,"format":"proof-v1","results":{"v1":True}} for n in ("python","rust","go")];result=certify_proofs(implementations,[{"id":"v1"}],[{"rejected":True}]);self.assertEqual(result["status"],"certified");self.assertEqual(len(result["certificate_hash"]),64)
  self.assertEqual(certify_proofs(implementations[:2],[{"id":"v1"}],[{"rejected":True}])["status"],"failed")
 def test_constitution_upgrade_protects_entrenched_rules(self):
  base={"entrenched":{"human_veto":True},"human_veto":True};impact={"tested":True,"critical_regressions":[]};vote={"yes_weight":80,"no_weight":20,"cast_weight":100,"quorum_weight":60};effective=datetime.now(timezone.utc)+timedelta(days=7)
  self.assertEqual(constitution_upgrade_gate(base,{"human_veto":True},impact,vote,effective,{"tested":True})["status"],"scheduled")
  self.assertEqual(constitution_upgrade_gate(base,{"human_veto":False},impact,vote,effective,{"tested":True})["status"],"blocked")
 def test_post_quantum_archive_forward_links_and_resigns_history(self):
  p=SimpleNamespace(object_id="x",content_hash="a"*64,algorithm="ml-dsa-65",historical_roots=["b"*64]);first=append_archive(None,p,1);previous=SimpleNamespace(archive_root=first["archive_root"]);second=append_archive(previous,p,2);self.assertEqual(second["previous_root"],first["archive_root"]);self.assertEqual(len(second["resignatures"]),1)
 def test_public_signal_diversity_and_epistemic_false_consensus(self):
  sources=[{"family":"official","owner":"a","proof":"1"},{"family":"academic","owner":"b","proof":"2"}];self.assertEqual(signal_quality(sources,{"risk":.2},["public_safety"])["status"],"published")
  result=epistemic_risk({"a":["b"],"b":["a"]},{"s1":"same","s2":"same"},[{"answer":"yes","evidence_root":"r"} for _ in range(5)],{"manipulation_score":.8});self.assertEqual(result["gate_status"],"blocked");self.assertIn("evidence_cycle",result["findings"]);self.assertIn("consensus_hallucination",result["findings"])
 def test_multi_asset_clearing_conserves_and_stress_opens_circuit(self):
  obligations=[{"from":"a","to":"b","asset":"USD","amount":100},{"from":"b","to":"a","asset":"EUR","amount":50}];result=clear_assets({"USD":1000,"EUR":1000},obligations,{"USD":1,"EUR":1.2},{"USD":1000},.2);self.assertTrue(result["stress_result"]["conserved"])
  failed=clear_assets({"USD":1000},[{"from":"a","to":"b","asset":"USD","amount":5000}],{"USD":1},{"USD":10},.5);self.assertEqual(failed["circuit_state"],"open")
 def test_fair_allocation_is_explainable_and_capacity_bounded(self):
  requests=[{"requester":"hospital","requested":70,"urgency":1,"vulnerability":1,"public_interest":1,"historical_share":.1},{"requester":"vendor","requested":70,"urgency":.3,"vulnerability":.2,"public_interest":.2,"historical_share":.8}];result=fair_allocate(100,requests);self.assertLessEqual(sum(x["amount"] for x in result["allocations"]),100);self.assertEqual(len(result["explanation_proof"]["signature"]),64);self.assertGreater(result["allocations"][0]["score"],result["allocations"][1]["score"])
 def test_ten_year_scenario_and_intergenerational_audit_are_deterministic(self):
  drivers={"climate":[.1,.2,.3],"technology":[.2,.2,.2]};first=long_horizon(drivers,10,[]);second=long_horizon(drivers,10,[]);self.assertEqual(len(first["risk_path"]),11);self.assertEqual(first["replay_hash"],second["replay_hash"])
  audit=commitment_audit({"coverage":.5},{"coverage":.8},{"future":-10},{"carbon":-5},["future"]);self.assertTrue(audit["passed"])
 def test_sovereign_stack_reproducible_offline_build_and_upgrade(self):
  capabilities=["identity","policy","audit","upgrade"];self.assertEqual(build_gate("s","a"*64,"a"*64,{"verified":True},capabilities),"verified");self.assertEqual(upgrade_gate("verified",True,{"passed":True},{"verified":True}),"ready");self.assertEqual(upgrade_gate("blocked",True,{"passed":True},{"verified":True}),"blocked")
if __name__=="__main__":unittest.main()
