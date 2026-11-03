"""Single opted-in official-Meta investigation against an existing disposable fault.

This wrapper NEVER injects a fault, verifies a sandbox, repairs, resets, or
retries a paid request. The existing controller is still the safety authority.
Use it from a terminal with an interactive TTY; credentials are not logged.
"""
from __future__ import annotations

import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import subprocess
import sys

CONSENT = "SEND DISPOSABLE LAB PROBE DATA TO HOSTED MUSE"
MODEL_LABEL = "hosted-muse:official-meta:muse-spark-1.3"
MAX_HOSTED_REQUESTS = 10


def _status(root: Path) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "proofops.real_lab", "status"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise ValueError("Disposable Docker lab status failed; no inference attempted")
    try:
        state = json.loads(result.stdout)
    except ValueError:
        raise ValueError("Disposable Docker lab returned an invalid status") from None
    if not isinstance(state, dict):
        raise ValueError("Disposable Docker status is not an object")
    return state


def _preflight(state: dict, expected_incident: str) -> None:
    incident = state.get("active_incident")
    if not isinstance(incident, dict):
        raise ValueError("No active incident; inject a disposable fault separately")
    if state.get("service_status") != "critical":
        raise ValueError("Only a currently degraded disposable lab can be investigated")
    if incident.get("id") != expected_incident:
        raise ValueError("Incident identity differs from explicit operator selection")
    if incident.get("status") not in ("open", "diagnosed"):
        raise ValueError("Incident already verified/recovered or not investigable")
    if incident.get("verification") is not None:
        raise ValueError("Prior independent verification already exists")
    if state.get("fingerprint") != incident.get("evidence_fingerprint"):
        raise ValueError("Live evidence changed since injection; refuse stale observations")
    if (str(incident.get("diagnostic_source", "")).startswith("hosted-muse:")
            and (incident.get("evidence_gate") or {}).get("allowed") is True):
        raise ValueError("Qualified hosted diagnosis is locked; no further model calls")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="One explicitly approved hosted Meta investigation; no injection, repair or retry"
    )
    parser.add_argument("--incident", required=True, help="Exact live incident ID from status")
    parser.add_argument("--output", required=True, help="New private report path; must not exist")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    output = Path(args.output).expanduser()
    if output.exists() or output.is_symlink():
        print("ABORT: report already exists; refusing overwrite", file=sys.stderr)
        return 2
    if not output.parent.is_dir():
        print("ABORT: output parent directory missing", file=sys.stderr)
        return 2
    try:
        state = _status(root)
        _preflight(state, args.incident)
    except ValueError as exc:
        print("ABORT: " + str(exc), file=sys.stderr)
        return 2

    print("Bravon official Meta Muse — single disposable incident")
    print("Project:", state.get("project"))
    print("Incident:", args.incident)
    print("Current revision:", state.get("revision"))
    print("Current service: critical")
    print("Max potentially billable requests:", MAX_HOSTED_REQUESTS)
    print("No fault injection, automatic repair, reset, or repeat is permitted.")
    if input("Type YES to authorize these hosted requests: ").strip() != "YES":
        print("Cancelled; no inference attempted.")
        return 0

    key = getpass("Official Meta API key (hidden): ").strip()
    if not key:
        print("ABORT: empty key; no inference attempted", file=sys.stderr)
        return 2

    # Human review/key entry may take time. Recheck controller revision and
    # live fault fingerprint before the first potentially billable request.
    try:
        refreshed = _status(root)
        _preflight(refreshed, args.incident)
        if (refreshed.get("revision") != state.get("revision")
                or refreshed.get("fingerprint") != state.get("fingerprint")):
            raise ValueError("Incident revision or fingerprint changed during approval")
    except ValueError as exc:
        del key
        print("ABORT: " + str(exc) + "; no hosted requests made", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env["MODEL_API_KEY"] = key
    del key
    command = [
        sys.executable, "-m", "proofops.real_lab", "investigate",
        "--investigator", "hosted-muse",
        "--muse-provider", "official-meta",
        "--confirm-cloud", CONSENT,
    ]
    original_umask = os.umask(0o077)
    try:
        # Exclusive create blocks accidental overwrite/replays of one report.
        with output.open("x", encoding="utf-8") as target:
            result = subprocess.run(
                command, cwd=root, env=env, stdout=target,
                stderr=subprocess.PIPE, text=True, check=False,
            )
    finally:
        os.umask(original_umask)
        env.pop("MODEL_API_KEY", None)

    if result.returncode:
        # Do not auto-retry a potentially billable API call or dump provider data.
        print("Hosted investigation failed; no retry performed. Exit:", result.returncode,
              file=sys.stderr)
        print("Partial report retained:", output)
        return result.returncode

    try:
        report = json.loads(output.read_text(encoding="utf-8"))
        incident = report.get("active_incident") or {}
        if incident.get("id") != args.incident:
            raise ValueError("Controller response incident ID changed")
        if incident.get("diagnostic_source") != MODEL_LABEL:
            raise ValueError("Controller response has unexpected model provenance")
        if report.get("service_status") != "critical":
            raise ValueError("Active service changed during read-only investigation")
    except (ValueError, AttributeError, TypeError):
        print("Reported investigation cannot be trusted; inspect saved evidence",
              file=sys.stderr)
        return 3

    usage = report.get("hosted_model_usage") or {}
    if not isinstance(usage, dict):
        usage = {}
    print("Model:", incident.get("diagnostic_source"))
    print("Raw action:", incident.get("raw_action"))
    print("Promoted action:", incident.get("action"))
    print("Evidence gate:", (incident.get("evidence_gate") or {}).get("allowed"))
    print("Hosted requests:", usage.get("requests"))
    print("Input/output tokens:", usage.get("input_tokens"), usage.get("output_tokens"))
    print("Active repair: NOT PERFORMED")
    print("Saved:", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
