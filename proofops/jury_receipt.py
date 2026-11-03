"""Privacy-minimized, locally generated jury receipt for the official Muse DNS experiment.

This module reads only owner-selected saved reports, executes the existing
offline audit, and exports a fixed, small set of non-sensitive values.
It never calls Meta, Docker, a network service, or a public upload endpoint.

A matching content digest provides alteration detection, NOT third-party
attestation that a model or Docker host executed the recorded work.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping

from .immortality import MODEL, digest, write_private
from .immortality_audit import audit_transfer
from .muse_matrix_report import score_report

SCHEMA = "bravon.jury-muse-receipt.v1"
EVIDENCE_LEVEL = "OFFLINE_CONTROLLER_CONSISTENCY_ONLY"
LIMITATIONS = (
    "Operator-controlled, self-digested evidence; NOT third-party or hardware "
    "attestation. One fixed DNS invariant and two predetermined System B "
    "candidates. No global immunity or production prevention established."
)
HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_REPORT_BYTES = 2_000_000


def _report(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Private input must be an existing regular file, not a symlink")
    if path.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError("Private input exceeded the two-megabyte audit limit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Private input must be a JSON object")
    return value


def _count(value: Any, minimum: int, maximum: int, label: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Missing or invalid " + label)
    return value


def build_receipt(
    source: Mapping[str, Any],
    destination: Mapping[str, Any],
    investigation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail closed unless the existing real-Docker/offline audit qualifies both reports."""
    audit = audit_transfer(source, destination)
    score = score_report(source, required_source=MODEL)
    investigation_score = score_report(
        source if investigation is None else investigation,
        required_source=MODEL,
    )
    if (score.get("source") != MODEL or score.get("scenario") != "dns-drift"
            or score.get("model_action") != "restore_dns"
            or score.get("promoted_action") != "restore_dns"
            or score.get("outcome") != "recovered"
            or score.get("model_correct") is not True
            or score.get("gate_allowed") is not True
            or score.get("sandbox_verified") is not True
            or score.get("active_recovered") is not True
            or score.get("integrity_errors")
            or score.get("missing_observations")
            or score.get("missing_citations")):
        raise ValueError("Source recovery does not satisfy official Muse qualification")
    if (investigation_score.get("incident_id") != score.get("incident_id")
            or investigation_score.get("scenario") != score.get("scenario")
            or investigation_score.get("model_action") != score.get("model_action")
            or investigation_score.get("promoted_action") != score.get("promoted_action")
            or investigation_score.get("gate_allowed") is not True
            or investigation_score.get("integrity_errors")
            or investigation_score.get("missing_observations")
            or investigation_score.get("missing_citations")):
        raise ValueError("Investigation report does not match qualified recovery")
    if (audit.get("verdict") != "STRUCTURALLY_CONSISTENT_CONTROLLER_REPORT"
            or audit.get("mode") != "REAL_ISOLATED_DOCKER"
            or audit.get("origin_model") != MODEL
            or audit.get("origin_action") != "restore_dns"
            or audit.get("policy_family") != "dns-gateway-binding"
            or audit.get("destination") != "B"
            or audit.get("dangerous_case", {}).get("decision") != "BLOCK"
            or set(audit.get("dangerous_case", {}).get("failed_docker_checks", []))
               != {"dns-record", "e2e"}
            or audit.get("legitimate_case", {}).get("decision") != "ALLOW"
            or audit.get("legitimate_case", {}).get("all_five_docker_checks_passed") is not True
            or audit.get("active_destination_preserved") is not True
            or audit.get("cleanup_recorded") is not True):
        raise ValueError("Destination transfer does not satisfy bounded DNS qualification")

    requests = _count(investigation_score.get("hosted_requests"), 1, 10, "hosted request count")
    tools = _count(investigation_score.get("tool_calls"), 1, 12, "read-only evidence count")
    citations = _count(
        len(investigation_score.get("cited_ids") or []), 1, 12, "evidence citation count"
    )
    links = {
        "source_recovery_digest": audit.get("source_recovery_digest"),
        "destination_report_digest": audit.get("transfer_report_digest"),
    }
    if any(not isinstance(value, str) or not HEX.fullmatch(value) for value in links.values()):
        raise ValueError("Linked controller report digest is invalid")
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "evidence_level": EVIDENCE_LEVEL,
        "source": {
            "model": MODEL,
            "scenario": "dns-drift",
            "proposed_action": "restore_dns",
            "hosted_requests": requests,
            "read_only_evidence_items": tools,
            "cited_evidence_items": citations,
            "gate_allowed": True,
            "sandbox_checks_passed": 5,
            "active_recovered": True,
        },
        "transfer": {
            "rule_family": "dns-gateway-binding",
            "destination": "B",
            "dangerous_policy": "BLOCK",
            "dangerous_failed_checks": ["dns-record", "e2e"],
            "legitimate_policy": "ALLOW",
            "legitimate_checks_passed": 5,
            "active_preserved": True,
            "cleanup_recorded": True,
        },
        "links": links,
        "limitations": LIMITATIONS,
    }
    result["content_digest"] = digest(result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a private, privacy-minimized Muse + Immortality jury receipt"
    )
    parser.add_argument("--source-report", required=True, type=Path)
    parser.add_argument("--investigation-report", type=Path)
    parser.add_argument("--transfer-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        source = _report(args.source_report.expanduser())
        investigation = (
            _report(args.investigation_report.expanduser())
            if args.investigation_report else source
        )
        transfer = _report(args.transfer_report.expanduser())
        receipt = build_receipt(source, transfer, investigation)
        write_private(args.output.expanduser(), receipt)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print("JURY RECEIPT REFUSED: " + str(exc)[:200], file=sys.stderr)
        return 2
    print("Private jury receipt exported locally; no model, Docker, or upload call.")
    print("Receipt digest detects changes but does not attest model or Docker provenance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
