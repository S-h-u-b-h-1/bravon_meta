"""Independent semantic evidence gate for *proposed* ProofOps repair actions.

The gate sees only the probe observations and the model's proposal. It has no
access to synthetic fixture labels or the answer key. It never executes a repair
and never replaces a wrong model action with a supposedly correct one.

This is a conservative pre-verification filter, NOT a replacement for the
separate real-Docker sandbox verification and operator approval gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class EvidenceVerdict:
    allowed: bool
    reason: str
    required_evidence: tuple[str, ...] = ()

    def public(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "reason": self.reason,
                "required_evidence": list(self.required_evidence)}


def prerequisite_evidence_ids(action: str, observations: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """Minimum *coverage* needed before offering an action to an external model.

    Not a diagnosis, prediction, or safety approval. It consults observed
    topology solely to identify which backend is selected by the gateway;
    it never reads the synthetic fault label, desired action or model score.
    The independent `assess_proposal` performs all semantic checks afterwards.
    """
    base = ("topology", "customer-path", "dns", "gateway")
    if action == "none":
        return ()
    if action == "restore_proxy":
        return (*base, "backend-a")
    if action == "failover":
        return (*base, "backend-a", "backend-b")
    if action != "restore_dns":
        raise ValueError("Unsupported repair action")

    seen = {row.get("evidence_id"): row for row in observations
            if isinstance(row, Mapping) and isinstance(row.get("evidence_id"), str)}
    topo = seen.get("topology", {})
    gateway = seen.get("gateway", {})
    declared = topo.get("declared_backends") if isinstance(topo, Mapping) else None
    upstream = gateway.get("upstream_ip") if isinstance(gateway, Mapping) else None
    if isinstance(declared, Mapping):
        for backend in ("backend-a", "backend-b"):
            if isinstance(upstream, str) and upstream == declared.get(backend):
                return (*base, backend)
    # An unknown or invalid selected upstream demands broader investigation,
    # not permission to repair based on an arbitrary single backend probe.
    return (*base, "backend-a", "backend-b")


def assess_proposal(proposal: Mapping[str, Any] | None,
                    observations: Sequence[Mapping[str, Any]]) -> EvidenceVerdict:
    """Fail closed on missing, contradictory or unsupported repair evidence.

    An abstention remains an abstention, regardless of whether a repair was
    possible. Correctness is scored separately by the evaluator's hidden label.
    """
    if not isinstance(proposal, Mapping):
        return EvidenceVerdict(False, "No valid model proposal")
    action = proposal.get("action")
    if action not in {"none", "restore_dns", "restore_proxy", "failover"}:
        return EvidenceVerdict(False, "Action is not allowlisted")
    if action == "none":
        return EvidenceVerdict(True, "Model abstained; no repair requested")

    seen: dict[str, Mapping[str, Any]] = {}
    for obs in observations:
        if not isinstance(obs, Mapping):
            return EvidenceVerdict(False, "Malformed read-only evidence")
        eid = obs.get("evidence_id")
        if not isinstance(eid, str) or eid in seen:
            return EvidenceVerdict(False, "Missing or duplicate evidence identity")
        seen[eid] = obs

    cited = proposal.get("evidence_ids")
    if (not isinstance(cited, list) or
        not all(isinstance(x, str) for x in cited) or
        len(set(cited)) != len(cited) or
        not set(cited).issubset(seen)):
        return EvidenceVerdict(False, "Citations must reference unique observed evidence")

    base = ("topology", "customer-path", "dns", "gateway")
    if not all(eid in seen and eid in cited for eid in base):
        return EvidenceVerdict(False, "Missing cited topology, customer, DNS or gateway evidence", base)

    topo, customer, dns, gateway = (seen[x] for x in base)
    if customer.get("healthy") is not False:
        return EvidenceVerdict(False, "Customer path is healthy or its status is unknown", base)
    declared = topo.get("declared_backends")
    if not isinstance(declared, Mapping):
        return EvidenceVerdict(False, "Declared backend topology unavailable", base)
    a_ip, b_ip = declared.get("backend-a"), declared.get("backend-b")
    edge_ip = topo.get("expected_gateway_ip")
    if not all(isinstance(x, str) and x for x in (a_ip, b_ip, edge_ip)):
        return EvidenceVerdict(False, "Declared IP identities unavailable", base)
    if dns.get("expected_ip") != edge_ip or gateway.get("declared_ips") != [a_ip, b_ip]:
        return EvidenceVerdict(False, "Observed configuration contradicts declared topology", base)

    selected_ip = gateway.get("upstream_ip")
    expected_dns = dns.get("matches_expected")
    allowed_gateway = gateway.get("allowed")

    if action == "restore_dns":
        if expected_dns is not False or dns.get("resolved_ip") == edge_ip:
            return EvidenceVerdict(False, "DNS drift was not established", base)
        if allowed_gateway is not True or selected_ip not in (a_ip, b_ip):
            return EvidenceVerdict(False, "Gateway is invalid; DNS repair alone cannot be proven", base)
        backend_id = "backend-a" if selected_ip == a_ip else "backend-b"
        required = (*base, backend_id)
        if backend_id not in seen or backend_id not in cited or seen[backend_id].get("healthy") is not True:
            return EvidenceVerdict(False, "Selected upstream health has not been proven", required)
        return EvidenceVerdict(True, "DNS repair justified by cited customer, topology and upstream probes", required)

    if action == "restore_proxy":
        required = (*base, "backend-a")
        if expected_dns is not True:
            return EvidenceVerdict(False, "DNS is wrong or unknown; proxy-only repair is not safe", required)
        if allowed_gateway is not False or selected_ip in (a_ip, b_ip):
            return EvidenceVerdict(False, "Invalid Nginx target not established", required)
        if "backend-a" not in seen or "backend-a" not in cited or seen["backend-a"].get("healthy") is not True:
            return EvidenceVerdict(False, "Healthy primary backend not established", required)
        return EvidenceVerdict(True, "Proxy repair justified by cited healthy target", required)

    required = (*base, "backend-a", "backend-b")
    if expected_dns is not True or allowed_gateway is not True or selected_ip != a_ip:
        return EvidenceVerdict(False, "Primary failover prerequisites not established", required)
    if (not all(x in seen and x in cited for x in ("backend-a", "backend-b")) or
        seen["backend-a"].get("healthy") is not False or
        seen["backend-b"].get("healthy") is not True):
        return EvidenceVerdict(False, "Failed primary and healthy standby not independently proven", required)
    return EvidenceVerdict(True, "Failover justified by cited primary and standby health", required)
