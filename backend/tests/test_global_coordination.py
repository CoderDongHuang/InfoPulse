import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models
from app.core.database import Base
from app.models.global_coordination import CrisisRoom, FederationNode
from app.models.user import User
from app.schemas.global_coordination import CrisisCommandCreate
from app.services.enterprise import provision_personal_tenant
from app.services.global_coordination import (
    aggregate_evaluation, append_crisis_command, apply_regulatory_delta,
    detect_drift, evaluate_contract, negotiate_protocol, reconcile_settlement,
    score_systemic_risk, verify_proof,
)


class GlobalCoordinationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    def test_three_node_protocol_negotiation_and_identity(self):
        a = FederationNode(protocol_versions=["2.0", "1.0"], capabilities=["proof", "settlement"], identity_fingerprint="a" * 64)
        b = FederationNode(protocol_versions=["3.0", "2.0"], capabilities=["proof", "crisis"], identity_fingerprint="b" * 64)
        c = FederationNode(protocol_versions=["2.0"], capabilities=["proof"], identity_fingerprint="c" * 64)
        self.assertEqual(negotiate_protocol(a, b, "b" * 64)["selected_version"], "2.0")
        self.assertEqual(negotiate_protocol(b, c, "c" * 64)["status"], "active")
        self.assertEqual(negotiate_protocol(a, c, "x" * 64)["status"], "blocked")

    def test_failed_online_proof_blocks_and_contract_is_bounded(self):
        proof = SimpleNamespace(expected_hash="a" * 64, observed_hash="b" * 64, signature_valid=True, chain_valid=True, proof_type="provenance", attestation={})
        self.assertEqual(verify_proof(proof)["status"], "blocked")
        result = evaluate_contract({"price": 120, "epsilon": .8}, {"price": {"max": 100}, "epsilon": {"max": .5}})
        self.assertEqual(result["status"], "countered")
        self.assertEqual(result["counter_offer"], {"price": 100, "epsilon": .5})

    def test_regulatory_conflict_risk_gate_and_drift(self):
        update = apply_regulatory_delta({"retention": 30}, {"set": {"retention": 7}}, False)
        self.assertEqual(update["status"], "conflict")
        self.assertEqual(score_systemic_risk({"concentration": .9, "cascade": .8}, .7)["gate_status"], "blocked")
        self.assertEqual(detect_drift({"mfa": False}, {"mfa": True})["status"], "drifted")

    def test_federated_evaluation_discards_samples_and_settlement_balances(self):
        result = aggregate_evaluation([{"accuracy": .8}, {"accuracy": .9}], {"verified": True})
        self.assertEqual(result["aggregate_metrics"]["accuracy"], .85)
        self.assertFalse(result["sample_retained"])
        self.assertNotIn("participant_metrics", result)
        self.assertTrue(reconcile_settlement(1000, 1.2, 100, 200, 900)["balanced"])
        with self.assertRaises(HTTPException):
            reconcile_settlement(1000, 1.2, 100, 200, 800)

    async def test_crisis_command_chain_is_forward_linked(self):
        async with self.sessions() as db:
            user = User(username="commander", email="commander@example.com", password_hash="x")
            db.add(user); await db.flush()
            org = await provision_personal_tenant(db, user); await db.flush()
            room = CrisisRoom(organization_id=org.id, name="Global drill", region_scope=["apac"], classification="restricted", commander_organization_id=org.id, participants=[org.id, "partner"], created_by=user.id)
            db.add(room); await db.flush()
            first = await append_crisis_command(db, org.id, user.id, room, CrisisCommandCreate(command_type="contain", classification="restricted", payload={"region": "apac"}))
            second = await append_crisis_command(db, org.id, user.id, room, CrisisCommandCreate(command_type="recover", classification="restricted", payload={"service": "exchange"}))
            self.assertEqual(second.previous_hash, first.chain_hash)
            self.assertNotEqual(second.chain_hash, first.chain_hash)


if __name__ == "__main__":
    unittest.main()
