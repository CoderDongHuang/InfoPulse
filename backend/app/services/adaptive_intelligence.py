from collections import deque

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.adaptive_intelligence import TransparencyLog
from app.services.trusted_ecosystem import digest, sign


def rollout_decision(compatibility: dict, health: dict) -> dict:
    compatible = bool(compatibility) and all(compatibility.values())
    healthy = health.get("error_rate", 1) <= health.get("max_error_rate", .02) and health.get("latency_ms", 10**9) <= health.get("max_latency_ms", 1000)
    return {"status": "canary" if compatible and healthy else "rolled_back", "rollback_reason": "" if compatible and healthy else "compatibility or canary health gate failed"}


def policy_gate(formal_result: dict, sandbox_diff: dict, approvers: list[str]) -> str:
    unique_approvers = set(approvers)
    safe_diff = not sandbox_diff.get("violations") and sandbox_diff.get("tested") is True
    return "approved" if formal_result.get("valid") is True and safe_diff and len(unique_approvers) >= 2 else "blocked"


async def append_transparency(db: AsyncSession, organization_id: str, payload) -> TransparencyLog:
    previous = await db.scalar(select(TransparencyLog).where(TransparencyLog.organization_id == organization_id).order_by(TransparencyLog.sequence.desc()))
    sequence = (previous.sequence + 1) if previous else 1
    leaf_hash = digest({"type": payload.object_type, "id": payload.object_id, "payload": payload.payload})
    previous_root = previous.merkle_root if previous else ""
    root = sign({"previous_root": previous_root, "leaf": leaf_hash, "sequence": sequence}, "transparency")
    row = TransparencyLog(organization_id=organization_id, sequence=sequence, object_type=payload.object_type, object_id=payload.object_id, leaf_hash=leaf_hash, previous_root=previous_root, merkle_root=root, witness_signatures=payload.witness_signatures, inclusion_proof=[leaf_hash, previous_root] if previous_root else [leaf_hash])
    db.add(row); await db.flush(); return row


def verify_inclusion(row: TransparencyLog) -> bool:
    expected = sign({"previous_root": row.previous_root, "leaf": row.leaf_hash, "sequence": row.sequence}, "transparency")
    return row.merkle_root == expected and row.leaf_hash in row.inclusion_proof


def simulate_cascade(topology: dict[str, list[str]], shocks: list[str]) -> dict:
    queue = deque((node, 0) for node in shocks); seen = set(); cascade = []
    while queue:
        node, depth = queue.popleft()
        if node in seen: continue
        seen.add(node); cascade.append({"node": node, "depth": depth})
        for target in topology.get(node, []): queue.append((target, depth + 1))
    total = max(len(topology), 1); risk = min(1, len(seen) / total)
    recovery = [f"isolate:{x['node']}" for x in sorted(cascade, key=lambda item: item["depth"], reverse=True)]
    return {"cascade_path": cascade, "recovery_plan": recovery, "risk_score": round(risk, 4), "replay_hash": digest({"topology": topology, "shocks": shocks})}


def market_gate(limit: int, haircut: float, anomaly_threshold: float, observed: float, stress_loss: int) -> dict:
    collateralized_capacity = round(limit * (1 - haircut))
    tripped = observed >= anomaly_threshold or stress_loss > collateralized_capacity
    return {"circuit_state": "open" if tripped else "closed", "stress_result": {"loss_cents": stress_loss, "capacity_cents": collateralized_capacity, "passed": not tripped}}


def select_sovereign_route(residency: str, constraints: dict, candidates: list[dict]) -> dict:
    allowed_models = set(constraints.get("allowed_models", []))
    eligible = [c for c in candidates if c.get("region") == residency and (not allowed_models or c.get("model") in allowed_models) and c.get("licensed") is True]
    if not eligible: return {"selected_region": "", "selected_model": "", "cross_border": False, "status": "blocked", "decision": {"reason": "no residency-safe licensed route"}}
    selected = min(eligible, key=lambda c: (c.get("latency_ms", 10**9), c.get("energy_wh", 10**9)))
    return {"selected_region": selected["region"], "selected_model": selected["model"], "cross_border": False, "status": "routed", "decision": {"candidate": selected, "evaluated": len(candidates)}}


def orchestrate_incident(signal: dict, playbooks: dict[str, list[str]]) -> dict:
    score = float(signal.get("score", 0)); severity = "critical" if score >= .9 else "high" if score >= .7 else "medium" if score >= .4 else "low"
    playbook = playbooks.get(severity, playbooks.get("default", []))
    return {"severity": severity, "playbook": playbook, "escalation": {"required": severity in {"critical", "high"}, "target": "global-commander" if severity == "critical" else "on-call"}, "timeline": [{"event": "detected"}, {"event": "classified", "severity": severity}, {"event": "playbook_started"}]}


def assurance_gate(age: int, pass_rate: float, max_age: int, minimum: float) -> dict:
    freshness = max(0, 1 - age / max_age); confidence = round(pass_rate * .7 + freshness * .3, 4)
    stale = age > max_age; return {"confidence": confidence, "gate_status": "allowed" if not stale and confidence >= minimum else "blocked", "sampling_plan": {"urgent": stale or confidence < minimum, "sample_percent": 100 if stale else 20}}


def sustainability_accounting(compute_wh: float, storage: float, transfer: float, carbon_factor: float, water_factor: float) -> dict:
    energy = compute_wh + storage * .02 + transfer * 12
    return {"energy_wh": round(energy, 4), "carbon_grams": round(energy * carbon_factor, 4), "water_ml": round(energy * water_factor, 4), "methodology": {"storage_wh_per_gb_hour": .02, "transfer_wh_per_gb": 12, "version": "1.0"}}


def governance_result(votes: list, eligible_weight: float, quorum_weight: float, veto_conditions: dict) -> dict:
    cast = sum(v.weight for v in votes); yes = sum(v.weight for v in votes if v.choice == "yes"); no = sum(v.weight for v in votes if v.choice == "no")
    vetoes = [v for v in votes if v.choice == "veto" and (not veto_conditions.get("requires_disclosure") or v.conflict_disclosed)]
    quorum = cast >= quorum_weight and cast <= eligible_weight
    passed = quorum and yes > no and not vetoes
    return {"cast_weight": cast, "yes_weight": yes, "no_weight": no, "quorum": quorum, "vetoed": bool(vetoes), "passed": passed}
