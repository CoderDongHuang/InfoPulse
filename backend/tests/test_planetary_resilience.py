import unittest
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from app.services.planetary_resilience import *


class PlanetaryResilienceTests(unittest.TestCase):
 def test_proof_mesh_threshold_and_revoked_dependency_gate(self):
  self.assertTrue(mesh_gate(True,["a","b"],2,[{"status":"available"}])["valid"])
  self.assertEqual(mesh_gate(True,["a","b"],2,[{"status":"revoked"}])["status"],"blocked")
  self.assertEqual(mesh_gate(True,["a","a"],2,[])["status"],"blocked")
 def test_hybrid_post_quantum_signature_preserves_historical_proofs(self):
  subject={"type":"policy","id":"p1"};result=hybrid_sign(subject,"ed25519","ml-dsa-65",[{"old":"proof"}])
  self.assertTrue(verify_hybrid(subject,result["hybrid_signature"]));self.assertEqual(len(result["historical_resignatures"]),1)
  result["hybrid_signature"]["post_quantum"]="tampered";self.assertFalse(verify_hybrid(subject,result["hybrid_signature"]))
 def test_planetary_twin_crosses_all_five_domains_deterministically(self):
  domains=["energy","communications","logistics","finance","information"];topology={"energy:grid":["communications:edge"],"communications:edge":["logistics:port"],"logistics:port":["finance:market"],"finance:market":["information:news"]}
  first=planetary_cascade(domains,topology,["energy:grid"]);second=planetary_cascade(domains,topology,["energy:grid"])
  self.assertEqual(first["systemic_score"],1);self.assertEqual(first["replay_hash"],second["replay_hash"])
 def test_agent_constitution_blocks_before_execution_and_human_veto(self):
  allowed=constitution_gate({"forbidden":{"external_write":True},"quorum_weight":5},{"external_write":False},{"cast_weight":10,"yes_weight":8,"no_weight":2},{})
  self.assertEqual(allowed["status"],"allowed")
  blocked=constitution_gate({"forbidden":{"external_write":True},"quorum_weight":5},{"external_write":True},{"cast_weight":10,"yes_weight":8,"no_weight":2},{"active":True,"evidence":"operator"});self.assertEqual(blocked["status"],"blocked");self.assertEqual(len(blocked["execution_proof"]["signature"]),64)
 def test_crisis_trade_settlement_and_refund_balance(self):
  listing=SimpleNamespace(capacity=5);trade=SimpleNamespace(status="allocated",amount_cents=1000,quantity=2,receipt={},settlement={})
  transition_trade(trade,listing,"deliver",{"capacity":2});transition_trade(trade,listing,"settle",{});self.assertTrue(trade.settlement["balanced"])
  trade2=SimpleNamespace(status="allocated",amount_cents=1000,quantity=2,receipt={},settlement={});transition_trade(trade2,listing,"refund",{});self.assertEqual(listing.capacity,7);self.assertTrue(trade2.settlement["balanced"])
 def test_dynamic_insurance_reserve_and_claim_conserve_funds(self):
  terms=insurance_terms({"cascade":.8,"concentration":.6},10000);self.assertGreater(terms["premium_cents"],100)
  policy=SimpleNamespace(trigger={"severity":"critical"},coverage_limit_cents=10000,reserve_cents=terms["reserve_cents"]);claim=insurance_claim(policy,{"severity":"critical"},5000);self.assertTrue(claim["balanced"]);self.assertEqual(claim["payout_cents"]+claim["remaining_reserve_cents"],terms["reserve_cents"])
 def test_memory_transfer_preserves_purpose_residency_retention_and_erases_source(self):
  memory=SimpleNamespace(allowed_purposes=["analysis"],expires_at=datetime.now(timezone.utc)+timedelta(days=10),status="active",memory_key="m1",content_hash="a"*64)
  result=memory_transfer_gate(memory,"analysis","eu","eu",datetime.now(timezone.utc)+timedelta(days=5));self.assertEqual(result["status"],"completed");self.assertTrue(result["source_erasure_proof"]["erased"])
  self.assertEqual(memory_transfer_gate(memory,"marketing","eu","us",datetime.now(timezone.utc)+timedelta(days=5))["status"],"blocked")
 def test_edge_mesh_converges_independent_of_input_order(self):
  a=SimpleNamespace(id="a",node_id="n1",sequence=1,vector_clock={"n1":1},chain_hash="a");b=SimpleNamespace(id="b",node_id="n2",sequence=1,vector_clock={"n2":1},chain_hash="b")
  self.assertEqual(converge_edge([a,b])["convergence_hash"],converge_edge([b,a])["convergence_hash"])
 def test_public_interest_commitment_is_observer_verifiable(self):
  result=public_commitment({"risk":.2},{"parity":.95},{"carbon":10},{"region_a":.5},["observer-b","observer-a","observer-a"]);self.assertEqual(len(result["public_commitment"]),64);self.assertEqual(len(result["observer_proofs"]),2)


if __name__=="__main__":unittest.main()
