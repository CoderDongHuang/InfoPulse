from collections import defaultdict
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.global_coordination import CrisisCommand, CrisisRoom, ProofVerification
from app.services.trusted_ecosystem import digest, sign, view


def negotiate_protocol(local, remote, presented_fingerprint: str) -> dict:
    versions = sorted(set(local.protocol_versions) & set(remote.protocol_versions), reverse=True)
    capabilities = sorted(set(local.capabilities) & set(remote.capabilities))
    identity_verified = remote.identity_fingerprint == presented_fingerprint
    return {
        "selected_version": versions[0] if versions else "",
        "agreed_capabilities": capabilities,
        "identity_verified": identity_verified,
        "status": "active" if versions and capabilities and identity_verified else "blocked",
        "compatibility": {"versions": versions, "missing_identity_trust": not identity_verified},
    }


def verify_proof(payload) -> dict:
    valid = payload.expected_hash == payload.observed_hash and payload.signature_valid and payload.chain_valid
    if payload.proof_type == "tee":
        valid = valid and bool(payload.attestation.get("measurement")) and payload.attestation.get("fresh") is True
    return {"status": "verified" if valid else "blocked", "valid": valid}


async def require_verified_proofs(db: AsyncSession, organization_id: str, subject_id: str) -> None:
    proofs = (await db.scalars(select(ProofVerification).where(
        ProofVerification.organization_id == organization_id,
        ProofVerification.subject_id == subject_id,
    ))).all()
    if not proofs or any(proof.status != "verified" for proof in proofs):
        raise HTTPException(409, "Online proof verification blocks execution")


def evaluate_contract(proposal: dict, constraints: dict) -> dict:
    violations = []
    counter = dict(proposal)
    for key, bounds in constraints.items():
        if key not in proposal or not isinstance(bounds, dict):
            continue
        value = proposal[key]
        if "max" in bounds and value > bounds["max"]:
            violations.append({"field": key, "rule": "max", "limit": bounds["max"]})
            counter[key] = bounds["max"]
        if "min" in bounds and value < bounds["min"]:
            violations.append({"field": key, "rule": "min", "limit": bounds["min"]})
            counter[key] = bounds["min"]
        if "allowed" in bounds and value not in bounds["allowed"]:
            violations.append({"field": key, "rule": "allowed", "limit": bounds["allowed"]})
    return {"status": "approval_pending" if not violations else "countered", "counter_offer": counter, "violations": violations}


def apply_regulatory_delta(existing: dict, delta: dict, emergency: bool) -> dict:
    rules = dict(existing)
    conflicts = []
    for key, value in delta.get("set", {}).items():
        if key in rules and rules[key] != value:
            conflicts.append({"rule": key, "old": rules[key], "new": value})
        rules[key] = value
    for key in delta.get("remove", []):
        rules.pop(key, None)
    return {"rules": rules, "conflicts": conflicts, "status": "withdrawn" if emergency else ("conflict" if conflicts else "active")}


def score_systemic_risk(factors: dict[str, float], threshold: float) -> dict:
    score = min(1.0, max(factors.values(), default=0) * .7 + (sum(factors.values()) / max(len(factors), 1)) * .3)
    return {"score": round(score, 4), "gate_status": "blocked" if score >= threshold else "allowed"}


def detect_drift(observed: dict, expected: dict) -> dict:
    drift = {key: {"expected": value, "observed": observed.get(key)} for key, value in expected.items() if observed.get(key) != value}
    remediation = [f"restore:{key}" for key in drift]
    return {"drift": drift, "remediation": remediation, "status": "drifted" if drift else "healthy"}


def blind_evidence(evidence: list[dict]) -> list[dict]:
    return [{k: v for k, v in item.items() if k not in {"tenant", "organization_id", "author", "email"}} for item in evidence]


def aggregate_evaluation(metrics: list[dict[str, float]], attestation: dict) -> dict:
    totals = defaultdict(float)
    counts = defaultdict(int)
    for row in metrics:
        for key, value in row.items():
            totals[key] += value
            counts[key] += 1
    aggregate = {key: round(total / counts[key], 6) for key, total in totals.items()}
    proof = {"aggregate_hash": digest(aggregate), "participant_count": len(metrics), "attestation": attestation}
    return {"aggregate_metrics": aggregate, "proof": proof, "sample_retained": False}


def reconcile_settlement(source_amount: int, fx_rate: float, withholding: int, escrow: int, payout: int) -> dict:
    converted = round(source_amount * fx_rate)
    balanced = withholding + escrow + payout == converted
    if not balanced:
        raise HTTPException(422, "Settlement is not balanced after FX conversion")
    return {"converted_cents": converted, "allocated_cents": withholding + escrow + payout, "balanced": True}


async def append_crisis_command(db: AsyncSession, organization_id: str, user_id: str, room: CrisisRoom, payload) -> CrisisCommand:
    if organization_id not in room.participants:
        raise HTTPException(403, "Organization is not a crisis-room participant")
    previous = await db.scalar(select(CrisisCommand).where(CrisisCommand.room_id == room.id).order_by(CrisisCommand.created_at.desc(), CrisisCommand.id.desc()))
    payload_hash = digest(payload.payload)
    previous_hash = previous.chain_hash if previous else ""
    chain_hash = sign({"previous": previous_hash, "type": payload.command_type, "payload": payload_hash, "actor": user_id}, "crisis")
    command = CrisisCommand(organization_id=organization_id, room_id=room.id, command_type=payload.command_type, actor_id=user_id, classification=payload.classification, payload_hash=payload_hash, previous_hash=previous_hash, chain_hash=chain_hash)
    db.add(command)
    await db.flush()
    return command
