import unittest
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.core.database import Base
from app.models.user import User
from app.schemas.adaptive_intelligence import TransparencyAppend
from app.services.adaptive_intelligence import *
from app.services.enterprise import provision_personal_tenant


class AdaptiveIntelligenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection: await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self): await self.engine.dispose()

    def test_protocol_canary_rolls_back_on_health_or_compatibility_failure(self):
        healthy = rollout_decision({"1->2": True, "2->3": True}, {"error_rate": .01, "max_error_rate": .02, "latency_ms": 80, "max_latency_ms": 100})
        failed = rollout_decision({"1->2": True, "2->3": False}, {"error_rate": .01, "max_error_rate": .02, "latency_ms": 80, "max_latency_ms": 100})
        self.assertEqual(healthy["status"], "canary"); self.assertEqual(failed["status"], "rolled_back")

    def test_autonomous_policy_requires_formal_sandbox_and_two_approvers(self):
        self.assertEqual(policy_gate({"valid": True}, {"tested": True, "violations": []}, ["a", "b"]), "approved")
        self.assertEqual(policy_gate({"valid": True}, {"tested": True, "violations": []}, ["a", "a"]), "blocked")

    async def test_transparency_log_has_verifiable_forward_roots(self):
        async with self.sessions() as db:
            user = User(username="witness", email="witness@example.com", password_hash="x"); db.add(user); await db.flush(); org = await provision_personal_tenant(db, user); await db.flush()
            first = await append_transparency(db, org.id, TransparencyAppend(object_type="model", object_id="m1", payload={"version": "1"}, witness_signatures=["w1"]))
            second = await append_transparency(db, org.id, TransparencyAppend(object_type="policy", object_id="p1", payload={"version": "2"}, witness_signatures=["w1", "w2"]))
            self.assertTrue(verify_inclusion(first)); self.assertTrue(verify_inclusion(second)); self.assertEqual(second.previous_root, first.merkle_root)

    def test_digital_twin_replays_cascade_and_market_circuit_opens(self):
        twin = simulate_cascade({"a": ["b", "c"], "b": ["d"], "c": [], "d": []}, ["a"])
        self.assertEqual(len(twin["cascade_path"]), 4); self.assertEqual(twin["risk_score"], 1)
        self.assertEqual(market_gate(1000, .2, .7, .8, 100)["circuit_state"], "open")

    def test_sovereign_route_never_crosses_residency_boundary(self):
        result = select_sovereign_route("cn", {"allowed_models": ["m1"]}, [{"region": "us", "model": "m1", "licensed": True, "latency_ms": 10}, {"region": "cn", "model": "m1", "licensed": True, "latency_ms": 30}])
        self.assertEqual(result["selected_region"], "cn"); self.assertFalse(result["cross_border"])
        self.assertEqual(select_sovereign_route("eu", {}, [{"region": "us", "model": "m1", "licensed": True}])["status"], "blocked")

    def test_incident_assurance_and_sustainability_gates(self):
        incident = orchestrate_incident({"score": .95}, {"critical": ["isolate", "notify"]}); self.assertEqual(incident["severity"], "critical")
        self.assertEqual(assurance_gate(48, .99, 24, .8)["gate_status"], "blocked")
        resources = sustainability_accounting(100, 10, 2, .5, .2); self.assertGreater(resources["energy_wh"], 100); self.assertEqual(resources["methodology"]["version"], "1.0")

    def test_governance_enforces_quorum_conflicts_and_veto(self):
        votes = [SimpleNamespace(choice="yes", weight=60, conflict_disclosed=False), SimpleNamespace(choice="no", weight=20, conflict_disclosed=False)]
        self.assertTrue(governance_result(votes, 100, 70, {})["passed"])
        votes.append(SimpleNamespace(choice="veto", weight=5, conflict_disclosed=True))
        self.assertFalse(governance_result(votes, 100, 70, {"requires_disclosure": True})["passed"])


if __name__ == "__main__": unittest.main()
