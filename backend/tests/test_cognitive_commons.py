import unittest
from types import SimpleNamespace
from fastapi import HTTPException
from app.services.cognitive_commons import *
class CognitiveCommonsTests(unittest.TestCase):
 def test_four_node_bft_consensus_tolerates_one_malicious_node(self):
  nodes=["a","b","c","d"];votes=[{"node":n,"decision":"available" if n!="d" else "revoked","signature_valid":True} for n in nodes];r=bft_consensus(nodes,votes,1);self.assertEqual(r["status"],"committed");self.assertEqual(r["decision"],"available");self.assertEqual(len(r["conflicts"]),1)
 def test_federated_constitutions_all_must_allow_action_and_entrenched_rules(self):
  constitutions=[{"organization":"a","permissions":["share"],"entrenched":{"human_veto":True}},{"organization":"b","permissions":["share"],"entrenched":{"human_veto":True}}];self.assertEqual(constitution_compatibility(constitutions,"share",{})["status"],"compatible");self.assertEqual(constitution_compatibility(constitutions,"share",{"human_veto":False})["status"],"blocked")
 def test_time_resilient_evidence_requires_joint_witnesses(self):
  r=preserve_evidence({"signature":"old"},"ml-dsa-65","future-pq",["w1","w2"]);self.assertEqual(r["status"],"preserved");self.assertTrue(r["joint_verification"]["old_valid"]);self.assertEqual(preserve_evidence({},"old","new",["w1"])["status"],"blocked")
 def test_causal_signal_requires_three_consistent_regions(self):
  experiments=[{"region":"cn","replicated":True,"effect":.2},{"region":"eu","replicated":True,"effect":.25},{"region":"us","replicated":True,"effect":.22}];self.assertEqual(causal_validate(experiments,[])["status"],"validated");self.assertEqual(causal_validate(experiments[:2],[])["status"],"review")
 def test_dissent_market_rewards_valid_minority_and_conserves_pool(self):
  positions=[{"participant":"a","position":"yes","source_family":"official","falsifiable":True},{"participant":"b","position":"yes","source_family":"official","falsifiable":False},{"participant":"c","position":"no","source_family":"academic","falsifiable":True,"evidence_valid":True}];r=settle_dissent(positions,1000);self.assertTrue(r["settlement"]["balanced"]);self.assertGreater(r["minority_reward_cents"],0)
 def test_public_treasury_accounting_is_balanced(self):
  r=reconcile_treasury(1000,[{"cents":500}],[{"cents":300}],[{"cents":200}],400);self.assertTrue(r["reconciliation"]["balanced"]);self.assertEqual(r["closing_cents"],600)
  with self.assertRaises(HTTPException):reconcile_treasury(0,[],[{"cents":100}],[],0)
 def test_allocation_appeal_replays_proof_and_compensates(self):
  allocation=SimpleNamespace(explanation_proof={"signature":"x"},allocations=[{"requester":"hospital","amount":20}]);r=appeal_allocation(allocation,[{"verified":True,"author":"blind"}],"hospital",30,100);self.assertTrue(r["decision"]["upheld"]);self.assertEqual(r["compensation_cents"],1000);self.assertNotIn("author",r["blind_evidence"][0])
 def test_century_scenario_safety_valve_and_federated_release(self):
  domains={x:[.1,.2,.3] for x in ["ai","climate","bio","energy","geopolitics"]};r=century_scenario(domains,100,[{"a":"ai","b":"energy","weight":.2}],[]);self.assertEqual(len(r["risk_path"]),11)
  valve=safety_valve_state(["a","b","c"],3,["identity","audit"],["a","b","c"],{"offline_degraded":True,"controlled_recovery":True});self.assertEqual(valve["state"],"recovering")
  build=SimpleNamespace(status="verified",artifact_digest="a"*64);release=federated_release_gate(build,[{"tier":1},{"tier":2}],{"signature_valid":True},[{"verified":True},{"verified":True}],{"v1":True});self.assertEqual(release["status"],"released")
if __name__=="__main__":unittest.main()
