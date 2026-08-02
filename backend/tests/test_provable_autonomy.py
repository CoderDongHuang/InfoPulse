import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import HTTPException

from app.schemas.provable_autonomy import DecisionProofCreate
from app.services.provable_autonomy import *


class ProvableAutonomyTests(unittest.TestCase):
    def test_decision_proof_blocks_constraint_failure_and_detects_tampering(self):
        valid = compile_decision_proof(DecisionProofCreate(action_id="a1", objective={"goal": "contain"}, constraints={"required_result": {"approved": True}}, evidence=[{"hash": "e1"}], policy={"version": 1}, result={"approved": True}))
        self.assertEqual(valid["status"], "executable"); self.assertTrue(verify_decision_proof(valid["proof"]))
        valid["proof"]["result"] = "tampered"; self.assertFalse(verify_decision_proof(valid["proof"]))
        blocked = compile_decision_proof(DecisionProofCreate(action_id="a2", objective={}, constraints={"required_result": {"approved": True}}, evidence=[{}], policy={}, result={"approved": False}))
        self.assertEqual(blocked["status"], "blocked")

    def test_model_checker_finds_sod_deadlock_and_unauthorized_counterexample(self):
        result = model_check(["draft", "approved"], [{"from": "draft", "to": "approved", "actor": "u1", "approver": "u1", "permission": "execute", "grants": ["read"]}], {"separation_of_duties": True, "no_deadlock": True, "terminal_states": []})
        self.assertEqual(result["status"], "failed"); self.assertTrue(result["counterexample"]); self.assertEqual(result["replay_hash"], model_check(["draft", "approved"], [{"from": "draft", "to": "approved", "actor": "u1", "approver": "u1", "permission": "execute", "grants": ["read"]}], {"separation_of_duties": True, "no_deadlock": True, "terminal_states": []})["replay_hash"])

    def test_three_region_replication_converges_deterministically(self):
        replicas = [{"region": "cn", "state": {"x": 1}, "vector_clock": {"cn": 2}, "healthy": False, "failover_priority": 1}, {"region": "eu", "state": {"x": 2}, "vector_clock": {"eu": 1}, "healthy": True, "failover_priority": 2}, {"region": "us", "state": {"y": 3}, "vector_clock": {"us": 3}, "healthy": True, "failover_priority": 3}]
        result = merge_replicas(replicas); self.assertEqual(result["status"], "converged"); self.assertEqual(result["active_region"], "eu"); self.assertTrue(result["conflicts"])

    def test_regulatory_partition_keeps_data_in_legal_region(self):
        result = partition_regulation("eu", {"blocked_capabilities": ["profiling"], "allowed_regions": ["eu"]}, ["search", "profiling"], [{"source_region": "eu", "target_region": "eu"}, {"source_region": "eu", "target_region": "us"}])
        self.assertEqual(result["capabilities"], ["search"]); self.assertEqual(len(result["legal_data_paths"]), 1)

    def test_memory_quarantine_and_erasure_proof(self):
        self.assertEqual(memory_gate(datetime.now(timezone.utc) + timedelta(days=1), .8)["status"], "quarantined")
        proof = erase_memory("m1", "a" * 64, "retention expired"); self.assertTrue(proof["erased"]); self.assertEqual(len(proof["proof"]), 64)

    def test_collective_hard_limits_and_collusion_gate(self):
        result = collective_gate(["a", "b"], {"a": ["b"], "b": []}, {"a": ["shell"], "b": []}, 100, 120, [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}], {"max_agents": 2, "max_delegation_depth": 1, "allowed_tools": ["read"], "collusion_threshold": .8})
        self.assertEqual(result["status"], "blocked"); self.assertIn("budget", result["violations"]); self.assertIn("collusion", result["violations"])

    def test_prediction_market_detects_concentration_and_balances_payout(self):
        positions = [SimpleNamespace(probability=.8, stake_cents=80), SimpleNamespace(probability=.4, stake_cents=20)]
        self.assertEqual(aggregate_forecasts(positions)["gate_status"], "blocked")
        settlement = settle_forecasts(positions, True, 1000); self.assertTrue(settlement["balanced"]); self.assertEqual(sum(settlement["payouts"]), 1000)

    def test_disaster_kernel_green_schedule_and_liability_gates(self):
        capabilities = ["identity", "policy", "audit", "alert", "manual_takeover"]
        self.assertEqual(disaster_kernel_gate(["payment", "model"], capabilities, {"verified": True}, {"tested": True})["gate_status"], "ready")
        schedule = green_schedule("cn", {"max_sla_ms": 100}, [{"region": "us", "window": "1", "available": True, "sla_ms": 10, "carbon_intensity": 1}, {"region": "cn", "window": "2", "available": True, "sla_ms": 50, "carbon_intensity": .2, "energy_wh": 10}]); self.assertEqual(schedule["selected_region"], "cn"); self.assertEqual(schedule["status"], "scheduled")
        result = liability_accounting(1000, 800, 100, 300, {"vendor": .75, "platform": .25}); self.assertTrue(result["reconciliation"]["balanced"]); self.assertEqual(sum(result["allocation"].values()), 800)
        with self.assertRaises(HTTPException): liability_accounting(1000, 700, 100, 100, {"vendor": 1})


if __name__ == "__main__": unittest.main()
