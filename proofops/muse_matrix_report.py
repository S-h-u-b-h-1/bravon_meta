"""Offline scoring of retained Bravon incident reports, without model/API calls.

The expected action is used ONLY after an investigation in this report reader.
It is never passed to the hosted investigator, and a plausible JSON report is
not independent proof that the model or Docker truly ran. Retain source logs.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Mapping

from .evidence_gate import prerequisite_evidence_ids

EXPECTED_ACTIONS = {
    "dns-drift": "restore_dns",
    "proxy-misroute": "restore_proxy",
    "backend-outage": "failover",
}
HEALTH_IDS = frozenset({
    "dns-record", "proxy-route", "upstream-health", "e2e", "standby",
})
ACTIONS = frozenset(EXPECTED_ACTIONS.values())


def _digest_valid(record: Any) -> bool:
    """Check the controller's content digest; not an external signature."""
    if not isinstance(record, dict):
        return False
    expected = record.get("proof_digest")
    if not isinstance(expected, str) or len(expected) != 64:
        return False
    payload = {key: value for key, value in record.items() if key != "proof_digest"}
    actual = sha256(json.dumps(
        payload, sort_keys=True, default=str, separators=(",", ":"),
    ).encode()).hexdigest()
    return actual == expected


def _five_healthy(checks: Any) -> bool:
    return (isinstance(checks, list)
            and len(checks) == 5
            and all(isinstance(row, dict) and row.get("passed") is True for row in checks)
            and {row.get("id") for row in checks} == HEALTH_IDS)


def score_report(report: Mapping[str, Any], *, required_source: str | None = None) -> dict[str, Any]:
    """Summarize a saved controller report; no I/O and no provider connections."""
    if not isinstance(report, Mapping):
        raise ValueError("Report must be a JSON object")
    incident = report.get("active_incident")
    if not isinstance(incident, Mapping):
        raise ValueError("Report has no active incident")
    scenario = incident.get("scenario")
    if scenario not in EXPECTED_ACTIONS:
        raise ValueError("Unknown or absent incident scenario")
    ident = incident.get("id")
    if not isinstance(ident, str) or not ident:
        raise ValueError("Incident identity is missing")
    source = incident.get("diagnostic_source")
    if not isinstance(source, str) or not source:
        raise ValueError("Investigation provenance is missing")
    if required_source and source != required_source:
        raise ValueError("Report source does not match --require-source")

    expected = EXPECTED_ACTIONS[scenario]
    raw = incident.get("raw_action")
    promoted = incident.get("action")
    gate = incident.get("evidence_gate")
    if not isinstance(gate, Mapping):
        raise ValueError("Report does not contain an independent evidence verdict")
    allowed = gate.get("allowed") is True
    investigation = incident.get("investigation")
    if not isinstance(investigation, Mapping):
        raise ValueError("Report has no retained investigation transcript")
    proposal = investigation.get("proposal")
    transcript = investigation.get("transcript")
    if not isinstance(proposal, Mapping) or not isinstance(transcript, list):
        raise ValueError("Investigation proposal or transcript is missing")
    if proposal.get("action") != raw:
        raise ValueError("Stored raw action differs from original model proposal")
    observed: list[dict[str, Any]] = []
    for row in transcript:
        if not isinstance(row, Mapping):
            raise ValueError("Malformed transcript step")
        if row.get("kind") == "tool":
            evidence = row.get("evidence")
            if not isinstance(evidence, dict) or not isinstance(evidence.get("evidence_id"), str):
                raise ValueError("Malformed tool observation")
            observed.append(evidence)
    ids = [row["evidence_id"] for row in observed]
    if len(ids) != len(set(ids)):
        raise ValueError("Repeated tool evidence IDs")
    citations = proposal.get("evidence_ids")
    if not isinstance(citations, list) or any(not isinstance(x, str) for x in citations):
        raise ValueError("Model citations must be an array of strings")
    if len(citations) != len(set(citations)) or not set(citations) <= set(ids):
        raise ValueError("Model cited duplicate or unobserved evidence")
    if raw != "none" and raw not in ACTIONS:
        raise ValueError("Model action is not allowlisted")
    required = prerequisite_evidence_ids(raw, observed)
    missing_observed = [eid for eid in required if eid not in ids]
    missing_cited = [eid for eid in required if eid not in citations]

    validation_errors: list[str] = []
    if promoted in ACTIONS and (not allowed or promoted != raw):
        validation_errors.append("Promoted an action not accepted by evidence gate")
    if promoted not in ACTIONS and promoted != "none":
        validation_errors.append("Unrecognized promoted action")
    if raw == "none" and promoted != "none":
        validation_errors.append("Model abstention was overwritten")
    if raw in ACTIONS and raw != expected and promoted == raw:
        validation_errors.append("Incorrect repair promoted for known injected fault")
    if raw in ACTIONS and allowed and (missing_observed or missing_cited):
        validation_errors.append("Gate accepted a proposal without cited prerequisites")

    verification = incident.get("verification")
    clone_valid = False
    if verification is not None:
        clone_valid = (
            isinstance(verification, dict)
            and verification.get("success") is True
            and _digest_valid(verification)
            and verification.get("action") == raw
            and _five_healthy(verification.get("sandbox_after"))
            and verification.get("source_fingerprint") == incident.get("evidence_fingerprint")
        )
        if incident.get("status") in ("verified", "recovered") and not clone_valid:
            validation_errors.append("Independent verification proof inconsistent or invalid")
    elif incident.get("status") in ("verified", "recovered"):
        validation_errors.append("Claimed verification missing")

    proof = incident.get("proof")
    recovery_valid = False
    if proof is not None:
        recovery_valid = (
            isinstance(proof, dict)
            and _digest_valid(proof)
            and clone_valid
            and proof.get("verification_digest") == verification.get("proof_digest")
            and proof.get("before_fingerprint") == verification.get("source_fingerprint")
            and proof.get("action") == raw == promoted == expected
            and proof.get("diagnostic_source") == source
            and proof.get("result") == "observed-recovery-in-disposable-docker-lab"
            and report.get("service_status") == "healthy"
            and _five_healthy(report.get("checks"))
            and incident.get("status") == "recovered"
        )
        if not recovery_valid:
            validation_errors.append("Active recovery proof inconsistent or invalid")
    elif incident.get("status") == "recovered":
        validation_errors.append("Claimed active recovery lacks a proof")

    usage = report.get("hosted_model_usage")
    if not isinstance(usage, Mapping):
        usage = {}
    model_correct = raw == expected
    blocked_wrong_repair = raw in ACTIONS and raw != expected and promoted == "none"
    outcome = (
        "recovered" if recovery_valid else
        "sandbox_verified" if clone_valid else
        "gate_accepted" if allowed and raw in ACTIONS and promoted == raw else
        "abstained" if raw == "none" else
        "rejected" if promoted == "none" else
        "unqualified"
    )
    return {
        "scenario": scenario,
        "incident_id": ident,
        "source": source,
        "expected_action": expected,
        "model_action": raw,
        "model_correct": model_correct,
        "promoted_action": promoted,
        "gate_allowed": allowed,
        "gate_reason": gate.get("reason"),
        "observed_ids": ids,
        "cited_ids": citations,
        "missing_observations": missing_observed,
        "missing_citations": missing_cited,
        "tool_calls": len(ids),
        "hosted_requests": usage.get("requests"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "blocked_wrong_repair": blocked_wrong_repair,
        "sandbox_verified": clone_valid,
        "active_recovered": recovery_valid,
        "outcome": outcome,
        "integrity_errors": validation_errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only offline scorer of saved Bravon incident reports; never calls models or Docker"
    )
    parser.add_argument("reports", nargs="+", help="One or more saved controller JSON report paths")
    parser.add_argument("--require-source", help="Exact model provenance required for every report")
    parser.add_argument("--json", action="store_true", help="Print machine-readable scoring summary")
    args = parser.parse_args(argv)
    scored = []
    try:
        for arg in args.reports:
            path = Path(arg).expanduser()
            document = json.loads(path.read_text(encoding="utf-8"))
            record = score_report(document, required_source=args.require_source)
            record["file"] = str(path)
            scored.append(record)
    except (OSError, ValueError, TypeError) as exc:
        print("Report audit failed: " + str(exc), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"report_schema": "bravon.muse-offline-matrix.v1",
                          "cases": scored,
                          "summary": {
                              "total": len(scored),
                              "model_correct": sum(x["model_correct"] for x in scored),
                              "blocked_wrong_repair": sum(x["blocked_wrong_repair"] for x in scored),
                              "recovered": sum(x["active_recovered"] for x in scored),
                              "integrity_errors": sum(bool(x["integrity_errors"]) for x in scored),
                          }}, indent=2))
    else:
        print("SCENARIO          MODEL           EXPECTED        GATE  RESULT")
        for case in scored:
            print(f"{case['scenario']:<18}{str(case['model_action']):<16}"
                  f"{case['expected_action']:<16}"
                  f"{'PASS' if case['gate_allowed'] else 'BLOCK':<6}{case['outcome']}")
            for error in case["integrity_errors"]:
                print("  INTEGRITY ERROR: " + error)
        print(f"Cases: {len(scored)}; model correct: {sum(x['model_correct'] for x in scored)}; "
              f"blocked wrong repairs: {sum(x['blocked_wrong_repair'] for x in scored)}; "
              f"active recoveries: {sum(x['active_recovered'] for x in scored)}")
        print("Note: saved JSON is self-reported controller evidence, NOT authenticated provider provenance.")

    return 3 if any(case["integrity_errors"] for case in scored) else 0


if __name__ == "__main__":
    raise SystemExit(main())
