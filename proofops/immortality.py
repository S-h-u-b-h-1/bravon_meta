"""Bravon Immortality: portable, non-executable antibodies from verified incidents.

A model may propose a repair, but only a previously recovered, evidence-gated
incident can generate an antibody. This experimental compiler accepts three
closed-form rules. It never executes code, calls a model, or modifies Docker.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from hashlib import sha256
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from .evidence_gate import assess_proposal
from .muse_matrix_report import score_report

SCHEMA = "bravon.antibody.v1"
TRANSFER_SCHEMA = "bravon.immortality-transfer.v1"
MODEL = "hosted-muse:official-meta:muse-spark-1.3"
RULES = {
    "restore_dns": ("dns-gateway-binding",
                    "Candidate DNS answer must equal this system's declared gateway IP."),
    "restore_proxy": ("proxy-declared-backend",
                      "Candidate proxy upstream must be a declared backend IP."),
    "failover": ("selected-backend-healthy",
                 "Candidate upstream must be a declared, independently healthy backend."),
}
HEALTH_IDS = frozenset({"dns-record", "proxy-route", "upstream-health", "e2e", "standby"})


def digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")).hexdigest()


def _valid_hash(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def compile_antibody(recovery: Mapping[str, Any]) -> dict[str, Any]:
    """Extract a fixed rule only after independent gate, sandbox and actual recovery.

    Controller hashes detect incidental changes, but are not signatures or
    independent provider attestations. No raw IPs, paths or model text are exported.
    """
    scored = score_report(recovery, required_source=MODEL)
    if (not scored["model_correct"] or not scored["gate_allowed"]
            or not scored["active_recovered"] or scored["integrity_errors"]):
        raise ValueError("A correctly diagnosed, evidence-gated, recovered incident is required")
    inc = recovery["active_incident"]
    action = inc["raw_action"]
    if action not in RULES or inc.get("action") != action:
        raise ValueError("Only one of the three verified allowlisted actions is eligible")
    investigation = inc["investigation"]
    transcript = investigation.get("transcript")
    if not isinstance(transcript, list):
        raise ValueError("Original model evidence transcript missing")
    observations = [r["evidence"] for r in transcript if
                    isinstance(r, dict) and r.get("kind") == "tool" and
                    isinstance(r.get("evidence"), dict)]
    semantic = assess_proposal(investigation["proposal"], observations)
    if not semantic.allowed:
        raise ValueError("Original citations do not pass independent semantic revalidation")
    verification = inc["verification"]
    proof = inc["proof"]
    if (not _valid_hash(verification.get("proof_digest")) or
            not _valid_hash(proof.get("proof_digest"))):
        raise ValueError("Original recovery/verification digests missing")
    family, claim = RULES[action]
    result = {
        "schema": SCHEMA,
        "family": family,
        "rule": claim,
        "scope": "disposable-docker-lab-prototype",
        "origin": {
            "model": MODEL,
            "action": action,
            "verification_digest": verification["proof_digest"],
            "recovery_digest": proof["proof_digest"],
        },
        "limitations": "Closed-form policy; passing one rule does not prove whole-system safety.",
    }
    result["policy_digest"] = digest(result)
    return result


def validate_antibody(antibody: Mapping[str, Any]) -> tuple[str, str]:
    if not isinstance(antibody, Mapping) or set(antibody) != {
        "schema", "family", "rule", "scope", "origin", "limitations", "policy_digest",
    }:
        raise ValueError("Invalid antibody fields")
    if antibody.get("schema") != SCHEMA or antibody.get("scope") != "disposable-docker-lab-prototype":
        raise ValueError("Unknown antibody version or scope")
    origin = antibody.get("origin")
    if not isinstance(origin, Mapping) or set(origin) != {
        "model", "action", "verification_digest", "recovery_digest",
    } or origin.get("model") != MODEL:
        raise ValueError("Invalid source provenance")
    action = origin.get("action")
    if action not in RULES:
        raise ValueError("Unknown source action")
    family, rule = RULES[action]
    if antibody.get("family") != family or antibody.get("rule") != rule or \
            antibody.get("limitations") != "Closed-form policy; passing one rule does not prove whole-system safety.":
        raise ValueError("Unrecognized or changed policy semantics")
    if not _valid_hash(origin["verification_digest"]) or not _valid_hash(origin["recovery_digest"]):
        raise ValueError("Invalid origin digest")
    expected = digest({k: v for k, v in antibody.items() if k != "policy_digest"})
    if antibody.get("policy_digest") != expected:
        raise ValueError("Antibody content digest mismatch")
    return action, family


def _ipv4(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("IP must be a literal IPv4 address")
    try:
        normalized = str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError:
        raise ValueError("Invalid IPv4 address") from None
    if normalized != value:
        raise ValueError("IP must use canonical form")
    return normalized


def validate_topology(topology: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(topology, Mapping) or set(topology) != {"gateway_ip", "backends"}:
        raise ValueError("Destination topology must declare gateway and two backends")
    gateway = _ipv4(topology["gateway_ip"])
    backends = topology["backends"]
    if not isinstance(backends, Mapping) or set(backends) != {"backend-a", "backend-b"}:
        raise ValueError("Destination must declare both backend identities")
    validated = {}
    for name in ("backend-a", "backend-b"):
        info = backends[name]
        if not isinstance(info, Mapping) or set(info) != {"ip", "healthy"} or type(info["healthy"]) is not bool:
            raise ValueError("Backend identity and measured health are required")
        validated[name] = {"ip": _ipv4(info["ip"]), "healthy": info["healthy"]}
    if len({gateway, validated["backend-a"]["ip"], validated["backend-b"]["ip"]}) != 3:
        raise ValueError("Gateway and backend addresses must be distinct")
    return {"gateway_ip": gateway, "backends": validated}


def evaluate(antibody: Mapping[str, Any], topology: Mapping[str, Any],
             candidate: Mapping[str, Any]) -> dict[str, str]:
    """Evaluate proposed target values; NEVER write or execute the proposal."""
    _action, family = validate_antibody(antibody)
    top = validate_topology(topology)
    if not isinstance(candidate, Mapping) or set(candidate) != {
        "dns_answer_ip", "upstream_ip",
    }:
        raise ValueError("Candidate must declare DNS answer and Nginx upstream")
    dns_ip = _ipv4(candidate["dns_answer_ip"])
    upstream_ip = _ipv4(candidate["upstream_ip"])
    declared = {name: entry for name, entry in top["backends"].items()}
    if family == "dns-gateway-binding":
        ok = dns_ip == top["gateway_ip"]
        reason = "DNS resolves to destination gateway" if ok else "DNS would miss destination gateway"
    elif family == "proxy-declared-backend":
        ok = upstream_ip in {x["ip"] for x in declared.values()}
        reason = "Upstream is a declared backend" if ok else "Upstream is not a declared backend"
    else:
        ok = any(x["ip"] == upstream_ip and x["healthy"] for x in declared.values())
        reason = "Selected backend was independently healthy" if ok else \
                 "Selected backend is unavailable or not declared"
    return {"decision": "ALLOW" if ok else "BLOCK",
            "family": family, "reason": reason,
            "caveat": "This policy checks one invariant, not overall service correctness."}


def topology_for_slot(slot: int) -> dict[str, Any]:
    """Generated example topology, never a claim about an external network."""
    if type(slot) is not int or not 20 <= slot <= 218:
        raise ValueError("Demo Docker subnet slot must be in 20..218")
    prefix = f"10.223.{slot}"
    return {"gateway_ip": prefix + ".10",
            "backends": {"backend-a": {"ip": prefix + ".21", "healthy": True},
                         "backend-b": {"ip": prefix + ".22", "healthy": True}}}


def _unreachable_ip(topology: Mapping[str, Any]) -> str:
    top = validate_topology(topology)
    network = ipaddress.ip_network(top["gateway_ip"] + "/24", strict=False)
    excluded = {top["gateway_ip"], *(x["ip"] for x in top["backends"].values())}
    for octet in (99, 98, 97):
        addr = str(network.network_address + octet)
        if addr not in excluded:
            return addr
    raise ValueError("Could not derive controlled unreachable test address")


def nightmare_plan(antibody: Mapping[str, Any], topology: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Bounded deterministic hypotheses; not autonomous model-generated attacks."""
    _action, family = validate_antibody(antibody)
    top = validate_topology(topology)
    healthy = [item["ip"] for item in top["backends"].values() if item["healthy"]]
    if not healthy:
        raise ValueError("No healthy destination backend for control candidate")
    unreachable = _unreachable_ip(top)
    safe = {"dns_answer_ip": top["gateway_ip"], "upstream_ip": healthy[-1]}
    harmful = dict(safe)
    if family == "dns-gateway-binding":
        # Match the baseline primary route in the actual dangerous clone.
        harmful["upstream_ip"] = top["backends"]["backend-a"]["ip"]
        harmful["dns_answer_ip"] = unreachable
    elif family == "proxy-declared-backend":
        harmful["upstream_ip"] = unreachable
    else:
        unhealthy = [x["ip"] for x in top["backends"].values() if not x["healthy"]]
        harmful["upstream_ip"] = unhealthy[0] if unhealthy else unreachable
    cases = [
        {"name": "dangerous-change", "candidate": harmful, "expected": "BLOCK"},
        {"name": "legitimate-control", "candidate": safe, "expected": "ALLOW"},
    ]
    for case in cases:
        case["assessment"] = evaluate(antibody, top, case["candidate"])
        if case["assessment"]["decision"] != case["expected"]:
            raise ValueError("Deterministic nightmare fixture violated its own expected result")
    return cases


def _source_gateway(recovery: Mapping[str, Any]) -> str:
    transcript = recovery["active_incident"]["investigation"]["transcript"]
    items = [entry["evidence"] for entry in transcript
             if isinstance(entry, Mapping) and entry.get("kind") == "tool" and
             isinstance(entry.get("evidence"), Mapping) and
             entry["evidence"].get("evidence_id") == "topology"]
    if len(items) != 1:
        raise ValueError("Original topology must have exactly one observation")
    return _ipv4(items[0]["expected_gateway_ip"])


def preview(recovery: Mapping[str, Any], *, destination_slot: int = 150) -> dict[str, Any]:
    antibody = compile_antibody(recovery)
    top = topology_for_slot(destination_slot)
    source_ip = _source_gateway(recovery)
    if source_ip == top["gateway_ip"] or \
       ipaddress.ip_network(source_ip + "/24", strict=False) == \
       ipaddress.ip_network(top["gateway_ip"] + "/24", strict=False):
        raise ValueError("Source and destination must use distinct network topologies")
    cases = nightmare_plan(antibody, top)
    result = {
        "schema": TRANSFER_SCHEMA,
        "mode": "SYNTHETIC_POLICY_PREVIEW_ONLY",
        "status": "policy-evaluated",
        "antibody": antibody,
        "destination": {"system": "B", "slot": destination_slot,
                        "different_from_source": True},
        "cases": [{"name": x["name"], "expected": x["expected"],
                   "decision": x["assessment"]["decision"],
                   "reason": x["assessment"]["reason"],
                   "docker_observed": False} for x in cases],
        "active_destination_remained_healthy": None,
        "cleanup_ok": None,
        "limitations": "No Docker ran; synthetic candidate values are not operational proof.",
    }
    result["report_digest"] = digest(result)
    return result


def valid_transfer_digest(report: Mapping[str, Any]) -> bool:
    if not isinstance(report, Mapping) or not _valid_hash(report.get("report_digest")):
        return False
    try:
        return report["report_digest"] == digest({
            k: v for k, v in report.items() if k != "report_digest"
        })
    except (TypeError, ValueError):
        return False


def write_private(path: Path, value: Mapping[str, Any]) -> None:
    if path.is_symlink() or path.exists() or path.parent.is_symlink() or not path.parent.is_dir():
        raise ValueError("Private output must be a new file in an existing normal directory")
    old = os.umask(0o077)
    try:
        with path.open("x", encoding="utf-8") as target:
            json.dump(value, target, indent=2, sort_keys=True, allow_nan=False)
            target.write("\n")
    finally:
        os.umask(old)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Bravon antibody compiler and preview")
    parser.add_argument("command", choices=("compile", "preview"))
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--slot", type=int, default=150)
    args = parser.parse_args(argv)
    try:
        recovery = json.loads(args.source_report.expanduser().read_text(encoding="utf-8"))
        result = compile_antibody(recovery) if args.command == "compile" else \
                 preview(recovery, destination_slot=args.slot)
        if args.output:
            write_private(args.output.expanduser(), result)
        else:
            print(json.dumps(result, indent=2, sort_keys=True))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print("Immortality refused: " + str(exc)[:300], file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
