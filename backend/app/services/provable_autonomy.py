from datetime import datetime, timezone

from fastapi import HTTPException

from app.services.trusted_ecosystem import digest, sign


def compile_decision_proof(p) -> dict:
    evidence_hashes = [digest(item) for item in p.evidence]; policy_hash = digest(p.policy); result_hash = digest(p.result)
    constraints_met = all(p.result.get(k) == v for k, v in p.constraints.get("required_result", {}).items())
    proof_body = {"action": p.action_id, "objective": digest(p.objective), "constraints": digest(p.constraints), "evidence": evidence_hashes, "policy": policy_hash, "result": result_hash, "constraints_met": constraints_met}
    proof = {**proof_body, "signature": sign(proof_body, "decision-proof")}
    verified = bool(evidence_hashes) and constraints_met
    return {"evidence_hashes": evidence_hashes, "policy_hash": policy_hash, "result_hash": result_hash, "proof": proof, "verified": verified, "status": "executable" if verified else "blocked"}


def verify_decision_proof(proof: dict) -> bool:
    body = {k: v for k, v in proof.items() if k != "signature"}
    return proof.get("signature") == sign(body, "decision-proof") and proof.get("constraints_met") is True


def model_check(states: list[str], transitions: list[dict], properties: dict) -> dict:
    violations = []
    for transition in transitions:
        if transition.get("from") not in states or transition.get("to") not in states: violations.append({"type": "invalid_state", "transition": transition})
        if properties.get("separation_of_duties") and transition.get("actor") == transition.get("approver"): violations.append({"type": "separation_of_duties", "transition": transition})
        if transition.get("permission") not in transition.get("grants", []): violations.append({"type": "unauthorized", "transition": transition})
    outgoing = {s: 0 for s in states}
    for transition in transitions:
        if transition.get("from") in outgoing: outgoing[transition["from"]] += 1
    if properties.get("no_deadlock"):
        for state, count in outgoing.items():
            if count == 0 and state not in properties.get("terminal_states", []): violations.append({"type": "deadlock", "state": state})
    counterexample = [violations[0]] if violations else []
    return {"violations": violations, "counterexample": counterexample, "replay_hash": digest({"states": states, "transitions": transitions, "counterexample": counterexample}), "status": "failed" if violations else "passed"}


def merge_replicas(replicas: list[dict]) -> dict:
    if len({r["region"] for r in replicas}) < 3: raise HTTPException(422, "At least three regions are required")
    merged_state = {}; merged_clock = {}; conflicts = []
    for replica in sorted(replicas, key=lambda r: r["region"]):
        for key, value in replica.get("state", {}).items():
            if key in merged_state and merged_state[key] != value: conflicts.append({"key": key, "values": [merged_state[key], value]})
            if key not in merged_state or digest(value) > digest(merged_state[key]): merged_state[key] = value
        for node, clock in replica.get("vector_clock", {}).items(): merged_clock[node] = max(merged_clock.get(node, 0), clock)
    healthy = sorted((r for r in replicas if r.get("healthy")), key=lambda r: r.get("failover_priority", 999))
    return {"state": merged_state, "vector_clock": merged_clock, "conflicts": conflicts, "active_region": healthy[0]["region"] if healthy else "", "convergence_hash": digest({"state": merged_state, "clock": merged_clock}), "status": "converged" if healthy else "unavailable"}


def partition_regulation(region: str, rules: dict, capabilities: list[str], data_paths: list[dict]) -> dict:
    allowed = [c for c in capabilities if c not in rules.get("blocked_capabilities", [])]
    legal_paths = [p for p in data_paths if p.get("source_region") == region and p.get("target_region") in rules.get("allowed_regions", [region])]
    conflicts = [{"capability": c, "reason": "blocked_by_regulation"} for c in capabilities if c not in allowed]
    return {"capabilities": allowed, "legal_data_paths": legal_paths, "conflicts": conflicts, "status": "active" if allowed and legal_paths else "restricted"}


def memory_gate(expires_at, contamination_score: float) -> dict:
    expired = expires_at <= datetime.now(timezone.utc); quarantined = contamination_score >= .7
    return {"status": "expired" if expired else "quarantined" if quarantined else "active", "quarantine_reason": "contamination threshold exceeded" if quarantined else ""}


def erase_memory(memory_key: str, content_hash: str, reason: str) -> dict:
    body = {"memory_key": memory_key, "previous_hash": content_hash, "reason": reason, "erased": True}
    return {**body, "proof": sign(body, "memory-erasure")}


def collective_gate(agent_ids: list[str], graph: dict[str, list[str]], grants: dict[str, list[str]], budget: int, spent: int, edges: list[dict], limits: dict) -> dict:
    violations = []
    if len(agent_ids) > limits.get("max_agents", 10): violations.append("agent_count")
    if spent > budget: violations.append("budget")
    allowed_tools = set(limits.get("allowed_tools", []))
    if any(tool not in allowed_tools for tools in grants.values() for tool in tools): violations.append("tool_grant")
    def depth(node, seen): return 99 if node in seen else max([0] + [1 + depth(child, seen | {node}) for child in graph.get(node, [])])
    if any(depth(agent, set()) > limits.get("max_delegation_depth", 3) for agent in agent_ids): violations.append("delegation_depth")
    pairs = {(e.get("from"), e.get("to")) for e in edges}; reciprocal = sum(1 for a, b in pairs if (b, a) in pairs); collusion = min(1, reciprocal / max(len(pairs), 1))
    if collusion >= limits.get("collusion_threshold", .8): violations.append("collusion")
    return {"collusion_score": round(collusion, 4), "violations": sorted(set(violations)), "status": "blocked" if violations else "running"}


def aggregate_forecasts(positions: list) -> dict:
    total = sum(p.stake_cents for p in positions)
    probability = sum(p.probability * p.stake_cents for p in positions) / total if total else .5
    concentration = max((p.stake_cents for p in positions), default=0) / total if total else 0
    return {"aggregate_probability": round(probability, 6), "manipulation_score": round(concentration, 6), "gate_status": "blocked" if concentration > .6 else "allowed"}


def settle_forecasts(positions: list, outcome: bool, liquidity: int) -> dict:
    scores = [1 - (p.probability - int(outcome)) ** 2 for p in positions]; total_score = sum(scores)
    payouts = [round(liquidity * score / total_score) if total_score else 0 for score in scores]
    if payouts: payouts[-1] += liquidity - sum(payouts)
    return {"scores": scores, "payouts": payouts, "balanced": sum(payouts) == liquidity}


def disaster_kernel_gate(unavailable: list[str], capabilities: list[str], identity: dict, takeover: dict) -> dict:
    required = {"identity", "policy", "audit", "alert", "manual_takeover"}; available = set(capabilities)
    healthy = required <= available and identity.get("verified") is True and takeover.get("tested") is True
    return {"audit_root": digest({"unavailable": unavailable, "capabilities": sorted(available)}), "gate_status": "ready" if healthy else "blocked"}


def green_schedule(residency: str, constraints: dict, candidates: list[dict]) -> dict:
    eligible = [c for c in candidates if c.get("region") == residency and c.get("available") and c.get("sla_ms", 10**9) <= constraints.get("max_sla_ms", 10**9)]
    if not eligible: return {"selected_region": "", "selected_window": "", "resource_proof": {}, "status": "blocked"}
    selected = min(eligible, key=lambda c: (c.get("carbon_intensity", 10**9), c.get("energy_wh", 10**9)))
    proof_body = {"workload_region": residency, "candidate": selected, "constraints": constraints}
    return {"selected_region": selected["region"], "selected_window": selected["window"], "resource_proof": {**proof_body, "signature": sign(proof_body, "green-schedule")}, "status": "scheduled"}


def liability_accounting(loss: int, compensation: int, recovery: int, reserve: int, parties: dict[str, float]) -> dict:
    if round(sum(parties.values()), 6) != 1: raise HTTPException(422, "Liability allocation must total 1")
    if compensation + reserve != loss + recovery: raise HTTPException(422, "Liability settlement is not balanced")
    allocation = {party: round(compensation * weight) for party, weight in parties.items()}
    if allocation: allocation[next(reversed(allocation))] += compensation - sum(allocation.values())
    return {"allocation": allocation, "reconciliation": {"debits_cents": compensation + reserve, "credits_cents": loss + recovery, "balanced": True}}
