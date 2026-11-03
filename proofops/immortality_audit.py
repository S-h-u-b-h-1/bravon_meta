"""Read-only audit of System A -> System B Immortality experiment reports.

This auditor cross-checks the recorded source recovery and destination
experiment, refusing manipulated/missing fields and impossible pass patterns.
The records are controller-authored and self-digested, NOT external attestation.
It neither contacts Meta nor starts, inspects, or modifies Docker containers.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
from pathlib import Path
import sys
from typing import Any

from .immortality import (
    HEALTH_IDS, MODEL, TRANSFER_SCHEMA, compile_antibody, preview,
    valid_transfer_digest, write_private,
)

AUDIT_SCHEMA = "bravon.immortality-audit.v1"
REPORT_FIELDS = frozenset({
    "schema", "mode", "status", "antibody", "destination", "cases",
    "active_destination_remained_healthy", "cleanup_ok", "limitations",
    "report_digest",
})
CASE_FIELDS = frozenset({
    "case", "clone_before", "clone_after", "observed",
    "expected_effect_observed", "policy_decision", "model_inference_performed",
})
CHECK_FIELDS = frozenset({"id", "passed"})
LIMITATIONS = (
    "Controller-generated origin proof is not independently signed. "
    "One DNS invariant is not universal system immunity."
)


def _checkset(checks: Any, *, failed: frozenset[str]) -> None:
    """Require five distinct fixed check names and the *exact* expected outcome."""
    if not isinstance(checks, list) or len(checks) != len(HEALTH_IDS):
        raise ValueError("Expected exactly five independent check records")
    seen: dict[str, bool] = {}
    for row in checks:
        if not isinstance(row, Mapping) or set(row) != CHECK_FIELDS:
            raise ValueError("Unexpected check record shape")
        identifier, passed = row["id"], row["passed"]
        if not isinstance(identifier, str) or identifier not in HEALTH_IDS or identifier in seen:
            raise ValueError("Unknown or repeated check identity")
        if type(passed) is not bool:
            raise ValueError("Health verdict must be a boolean")
        seen[identifier] = passed
    if set(seen) != HEALTH_IDS or {key for key, value in seen.items() if not value} != failed:
        raise ValueError("Observed check outcomes do not match the required physical signature")


def audit_transfer(
    recovery: Mapping[str, Any],
    transfer: Mapping[str, Any],
    *,
    allow_simulated: bool = False,
) -> dict[str, Any]:
    """Re-evaluate two immutable JSON inputs without external I/O.

    allow_simulated is only for offline unit tests. The CLI requires REAL mode.
    Even a valid REAL report remains controller-reported, not independently
    authenticated Docker or Meta-origin evidence.
    """
    policy = compile_antibody(recovery)
    if policy["family"] != "dns-gateway-binding":
        raise ValueError("The physically qualified Immortality v1 case is DNS-only")
    if not isinstance(transfer, Mapping) or set(transfer) != REPORT_FIELDS:
        raise ValueError("Unknown fields or missing evidence in transfer record")
    if transfer["schema"] != TRANSFER_SCHEMA:
        raise ValueError("Unknown transfer report schema")
    mode = transfer["mode"]
    if mode != "REAL_ISOLATED_DOCKER" and not (
        allow_simulated and mode == "SIMULATED_DOCKER_TEST"
    ):
        raise ValueError("Real isolated Docker report required; synthetic/test reports rejected")
    if transfer["status"] != "verified-experimental-transfer":
        raise ValueError("Only a fully successful transfer report may be qualified")
    if transfer["antibody"] != policy:
        raise ValueError("Transfer antibody differs from the original recovered incident")
    if transfer["limitations"] != LIMITATIONS:
        raise ValueError("Source evidence limitations were removed or changed")
    if not valid_transfer_digest(transfer):
        raise ValueError("Transfer content digest mismatch")
    if transfer["active_destination_remained_healthy"] is not True or transfer["cleanup_ok"] is not True:
        raise ValueError("Active System B preservation and cleanup were not both proven in the record")

    dest = transfer["destination"]
    if not isinstance(dest, Mapping) or set(dest) != {
        "system", "slot", "different_from_source",
    } or dest.get("system") != "B" or dest.get("different_from_source") is not True:
        raise ValueError("Destination identity or source independence missing")
    slot = dest.get("slot")
    if type(slot) is not int:
        raise ValueError("Destination network slot must be an integer")
    original_plan = preview(recovery, destination_slot=slot)
    if dest != original_plan["destination"]:
        raise ValueError("Destination topology differs from source-checked transfer plan")

    cases = transfer["cases"]
    if not isinstance(cases, list) or len(cases) != 2:
        raise ValueError("Both dangerous and legitimate control experiments are required")
    for index, (name, decision, expected_failures) in enumerate((
        ("dangerous-change", "BLOCK", frozenset({"dns-record", "e2e"})),
        ("legitimate-control", "ALLOW", frozenset()),
    )):
        row = cases[index]
        if not isinstance(row, Mapping) or set(row) != CASE_FIELDS:
            raise ValueError("Unexpected or incomplete experiment record fields")
        if row["case"] != name or row["policy_decision"] != decision:
            raise ValueError("Case identity or transferred policy decision is wrong")
        if row["policy_decision"] != original_plan["cases"][index]["decision"]:
            raise ValueError("Transferred policy disagrees with independently recomputed plan")
        if row["observed"] is not True or row["expected_effect_observed"] is not True:
            raise ValueError("System B experiment was not recorded as physically observed")
        if row["model_inference_performed"] is not False:
            raise ValueError("The destination experiment unexpectedly reported model inference")
        _checkset(row["clone_before"], failed=frozenset())
        _checkset(row["clone_after"], failed=expected_failures)

    # Only derive public-facing values from hard-coded fields after validating
    # the complete original object; never copy untrusted text or source logs.
    return {
        "audit_schema": AUDIT_SCHEMA,
        "verdict": "STRUCTURALLY_CONSISTENT_CONTROLLER_REPORT",
        "mode": mode,
        "origin_model": MODEL,
        "origin_action": "restore_dns",
        "policy_family": policy["family"],
        "source_recovery_digest": policy["origin"]["recovery_digest"],
        "transfer_report_digest": transfer["report_digest"],
        "destination": "B",
        "destination_slot": slot,
        "dangerous_case": {
            "decision": "BLOCK",
            "failed_docker_checks": ["dns-record", "e2e"],
            "other_docker_checks_passed": True,
        },
        "legitimate_case": {
            "decision": "ALLOW",
            "all_five_docker_checks_passed": True,
        },
        "active_destination_preserved": True,
        "cleanup_recorded": True,
        "limits": (
            "Self-digested operator-controller evidence, not cryptographic "
            "attestation of the model, Docker host, or independent runner. "
            "One DNS rule and two predetermined candidate changes only."
        ),
    }


def candidate_export(recovery: Mapping[str, Any],
                     transfer: Mapping[str, Any]) -> dict[str, Any]:
    """Produce only schema-checked, privacy-minimized local evidence.

    The existing viewer understands this unchanged transfer schema. This
    operation writes nothing unless the operator provides --export locally.
    It never commits, uploads or publishes a report.
    """
    audit_transfer(recovery, transfer)  # No simulated-to-real laundering.
    return json.loads(json.dumps(transfer, sort_keys=True, allow_nan=False))


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Source report is missing or symlinked")
    if path.stat().st_size > 2_000_000:
        raise ValueError("Report exceeds the private offline audit size limit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit a recovered Muse incident against a real System B report; no Docker or API calls"
    )
    parser.add_argument("--source-report", required=True, type=Path)
    parser.add_argument("--transfer-report", required=True, type=Path)
    parser.add_argument("--export", type=Path,
                        help="Optional new local JSON file for manual privacy review; never uploads")
    args = parser.parse_args(argv)
    try:
        recovery = _read_json(args.source_report.expanduser())
        transfer = _read_json(args.transfer_report.expanduser())
        summary = audit_transfer(recovery, transfer)
        if args.export:
            write_private(args.export.expanduser(), candidate_export(recovery, transfer))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("IMMORTALITY AUDIT REJECTED: " + str(exc)[:240], file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.export:
        print("Local export created for PRIVATE REVIEW ONLY; no upload or Git action performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
