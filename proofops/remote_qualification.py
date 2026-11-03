"""Owner-approved GitHub-hosted Docker qualification; NEVER a public execution API.

The runner creates only the repository's allowlisted disposable Compose stacks.
It executes the existing non-AI qualification controller, ensures cleanup,
validates its internal report, and exports only fixed, privacy-minimized results.

A GitHub Actions artifact and controller digests do NOT independently attest
the physical environment or establish performance on arbitrary infrastructure.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import signal
import threading
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Mapping

from .qualification import (
    RUN_CONFIRMATION, EXPECTED_ACTIONS, _verify_run,
    run_qualification, verify_report,
)
from .real_lab import DockerLab, _digest

SCHEMA = "bravon.remote-docker-qualification.v1"
CONSENT = "RUN BOUNDED REMOTE DOCKER QUALIFICATION"
REPO = "S-h-u-b-h-1/bravon"
SCENARIOS = ("dns-drift", "proxy-misroute", "backend-outage")
CHECK_IDS = ("dns-record", "proxy-route", "upstream-health", "e2e", "standby")
EXPECTED_FAULT_SIGNATURES = {
    "dns-drift": frozenset({"dns-record", "e2e"}),
    "proxy-misroute": frozenset({"proxy-route", "upstream-health", "e2e"}),
    "backend-outage": frozenset({"upstream-health", "e2e"}),
}
SLOT = 191
LOCAL_DOCKER_HOST = "unix:///var/run/docker.sock"
LOCAL_DOCKER_SOCKET = Path("/var/run/docker.sock")
REMOTE_DOCKER_CONTEXT_OVERRIDES = (
    "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH", "DOCKER_CONFIG",
)

class RemoteCancellation(RuntimeError):
    """The owner cancelled a disposable qualification; no green result is issued."""


@contextmanager
def _guarded_lifecycle():
    """Attempt cleanup on SIGTERM/SIGINT; never treat interruption as success.

    A hard SIGKILL, process/host crash or runner timeout cannot be intercepted.
    GH-hosted VM disposal is the additional isolation boundary, not an
    attested cleanup result.
    """
    if threading.current_thread() is not threading.main_thread():
        raise ValueError("Remote qualification must execute on the main thread")
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}

    def stop(signum, _frame):
        # Preserve cleanup time from repeated Ctrl+C/SIGTERM. Runner shutdown
        # can still force-kill the process before Docker down completes.
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        raise RemoteCancellation("Owner cancellation while operating a disposable lab")

    try:
        for sig in previous:
            signal.signal(sig, stop)
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


MAX_OUTPUT_BYTES = 100_000
LIMITATIONS = (
    "GitHub Actions runner and Docker controller report, not external attestation. "
    "Only predefined disposable DNS/proxy/backend faults, deterministic repair "
    "rules and five fixed health checks. No Meta Muse inference, customer "
    "infrastructure access, general self-healing or production certification."
)


def selected_scenarios(value: str) -> tuple[str, ...]:
    if value == "all":
        return SCENARIOS
    if value in SCENARIOS:
        return (value,)
    raise ValueError("Only the three fixed Docker scenarios or all are allowed")


def require_explicit_runner(environ: Mapping[str, str], confirmation: str) -> dict[str, str]:
    """Prohibit accidental local, PR-initiated, fork or unreviewed-branch execution."""
    if confirmation != CONSENT:
        raise ValueError("The exact remote Docker experiment confirmation is required")
    expected = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": REPO,
    }
    for key, value in expected.items():
        if environ.get(key) != value:
            raise ValueError("Remote runner authorization context is not approved: " + key)
    owner = "s-h-u-b-h-1"
    actor = environ.get("GITHUB_ACTOR", "")
    triggering_actor = environ.get("GITHUB_TRIGGERING_ACTOR", "")
    if actor.casefold() != owner or triggering_actor.casefold() != owner:
        raise ValueError("Only the repository owner may authorize or re-run this experiment")
    if environ.get("BRAVON_REMOTE_RUNNER_ENABLED") != "YES":
        raise ValueError("Owner-enabled repository variable is required for remote Docker execution")
    if environ.get("DOCKER_HOST") != LOCAL_DOCKER_HOST:
        raise ValueError("Remote qualification requires the runner's local Unix Docker socket")
    if any(environ.get(name) for name in REMOTE_DOCKER_CONTEXT_OVERRIDES):
        raise ValueError("Remote Docker context, TLS or credential overrides are forbidden")
    run_id = environ.get("GITHUB_RUN_ID", "")
    attempt = environ.get("GITHUB_RUN_ATTEMPT", "")
    sha = environ.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9]{1,20}", run_id):
        raise ValueError("Invalid GitHub run identity")
    if not re.fullmatch(r"[0-9]{1,3}", attempt):
        raise ValueError("Invalid GitHub run attempt")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Invalid exact GitHub source commit")
    temp = environ.get("RUNNER_TEMP", "")
    root = Path(temp)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("A normal, absolute ephemeral runner directory is required")
    return {"run_id": run_id, "attempt": attempt, "sha": sha, "runner_temp": str(root)}


def _checks(checks: Any) -> list[dict[str, Any]]:
    """Drop raw URLs, IPs, topology, Docker output and secrets."""
    if not isinstance(checks, list) or len(checks) != len(CHECK_IDS):
        raise ValueError("Exactly five recorded health checks are required")
    values: dict[str, bool] = {}
    for item in checks:
        if not isinstance(item, dict):
            raise ValueError("Unexpected health check representation")
        identity, passed = item.get("id"), item.get("passed")
        if identity not in CHECK_IDS or identity in values or type(passed) is not bool:
            raise ValueError("Duplicate, missing or invalid health check")
        values[identity] = passed
    if set(values) != set(CHECK_IDS):
        raise ValueError("Health check identity mismatch")
    return [{"id": name, "passed": values[name]} for name in CHECK_IDS]


def _require_known_fault(checks: list[dict[str, Any]], scenario: str) -> None:
    if scenario not in EXPECTED_FAULT_SIGNATURES:
        raise ValueError("Unknown fault signature")
    failed = frozenset(row["id"] for row in checks if row["passed"] is False)
    if failed != EXPECTED_FAULT_SIGNATURES[scenario]:
        raise ValueError("Observed incident differs from the expected fixed fault signature")


def build_minimal_receipt(
    report: Mapping[str, Any],
    *,
    requested: tuple[str, ...],
    identity: Mapping[str, str],
) -> dict[str, Any]:
    """Accept only full, internally valid qualification; never launder fake CI runs."""
    if not isinstance(report, Mapping):
        raise ValueError("Qualification report must be a dictionary")
    if report.get("schema_version") != "proofops-qualification-v1":
        raise ValueError("Qualification report schema differs")
    if report.get("runner_provenance") != "docker-cli-subprocess":
        raise ValueError("Injected fake-Docker runner cannot be presented as real")
    if report.get("model_used") is not False or report.get("diagnosis_provenance") != "deterministic rules over real probes":
        raise ValueError("Unknown or misrepresented model provenance")
    if requested not in ((SCENARIOS[0],), (SCENARIOS[1],), (SCENARIOS[2],), SCENARIOS):
        raise ValueError("Only one fixed scenario or all three in order can be qualified")
    if list(report.get("planned_scenarios", [])) != list(requested) or report.get("repeats") != 1:
        raise ValueError("Unexpected scenario selection or repeat count")
    if any(not isinstance(identity.get(x), str) for x in ("run_id", "attempt", "sha")):
        raise ValueError("Missing or malformed GitHub workflow identity")
    if (not re.fullmatch(r"[0-9]{1,20}", identity["run_id"])
            or not re.fullmatch(r"[0-9]{1,3}", identity["attempt"])
            or not re.fullmatch(r"[0-9a-f]{40}", identity["sha"])):
        raise ValueError("Invalid workflow identity")
    checksum = report.get("report_digest")
    if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise ValueError("Missing controller report content digest")
    if _digest({k: v for k, v in report.items() if k != "report_digest"}) != checksum:
        raise ValueError("Raw report digest mismatch")
    runs = report.get("runs")
    summary = report.get("summary")
    if not isinstance(runs, list) or not isinstance(summary, Mapping):
        raise ValueError("Qualification contains no complete run summary")
    if len(runs) != len(requested) or summary.get("complete") is not True or summary.get("failed") != 0:
        raise ValueError("Incomplete or failed Docker qualification")
    if summary.get("total") != len(requested) or summary.get("passed") != len(requested):
        raise ValueError("Summary count differs from actual qualification")
    reduced: list[dict[str, Any]] = []
    for index, scenario in enumerate(requested):
        result = runs[index]
        if not isinstance(result, dict) or result.get("scenario") != scenario:
            raise ValueError("Scenario identity/order mismatch")
        allowed, _reason = _verify_run(result)
        if not allowed or result.get("status") != "passed" or result.get("reset_to_healthy") is not True:
            raise ValueError("Real Docker observations cannot qualify this scenario")
        if result.get("expected_action") != EXPECTED_ACTIONS[scenario]:
            raise ValueError("Selected action differs from allowlisted repair")
        before = _checks(result["initial_failure_checks"])
        _require_known_fault(before, scenario)
        after = _checks(result["recovery_proof"]["after"])
        sandbox = _checks(result["verification"]["sandbox_after"])
        if all(x["passed"] for x in before) or not all(x["passed"] for x in after + sandbox):
            raise ValueError("Contradictory before/after probe evidence")
        reduced.append({
            "scenario": scenario,
            "action": EXPECTED_ACTIONS[scenario],
            "result": "PASSED",
            "before": before,
            "sandbox_after": sandbox,
            "recovery_after": after,
            "unapproved_repair_denied": True,
            "stale_revision_repair_denied": True,
            "cleanup_to_healthy": True,
        })
    result = {
        "schema": SCHEMA,
        "execution_mode": "GH_HOSTED_DISPOSABLE_DOCKER",
        "model_inference": "NONE_RULE_BASED_ONLY",
        "report_status": "QUALIFIED_CONTROLLER_REPORT",
        "run": {
            "repository": REPO,
            "run_id": identity["run_id"],
            "attempt": identity["attempt"],
            "commit": identity["sha"],
        },
        "requested_scenarios": list(requested),
        "results": reduced,
        "five_check_invariants": list(CHECK_IDS),
        "raw_controller_digest": checksum,
        "limitations": LIMITATIONS,
    }
    result["content_digest"] = _digest(result)
    if len(json.dumps(result).encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ValueError("Minimal evidence output exceeded fixed size limit")
    return result


def write_private_receipt(path: Path, data: Mapping[str, Any]) -> None:
    if path.exists() or path.is_symlink() or path.parent.is_symlink() or not path.parent.is_dir():
        raise ValueError("Output must be new inside an existing normal directory")
    with path.open("x", encoding="utf-8") as target:
        json.dump(data, target, sort_keys=True, separators=(",", ":"), allow_nan=False)
        target.write("\n")
    path.chmod(0o600)


def docker_preflight() -> None:
    if not LOCAL_DOCKER_SOCKET.is_socket():
        raise ValueError("Runner local Docker Unix socket is missing")
    try:
        status = subprocess.run(
            ["docker", "--host", LOCAL_DOCKER_HOST, "info", "--format", "{{.ServerVersion}}"],
            text=True, capture_output=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("Ephemeral runner Docker service unavailable") from exc
    if status.returncode or not status.stdout.strip():
        raise ValueError("Docker daemon is not healthy on this ephemeral runner")


def execute(
    selection: str,
    *,
    confirmation: str,
    environ: Mapping[str, str],
    docker_lab_factory=DockerLab,
) -> Path:
    """Run only after the explicit approved workflow_dispatch authorization."""
    chosen = selected_scenarios(selection)
    identity = require_explicit_runner(environ, confirmation)
    destination = Path(identity["runner_temp"]) / "bravon-remote-receipt.json"
    if destination.exists() or destination.is_symlink():
        raise ValueError("Remote receipt file already exists; refuse overwrite")
    with _guarded_lifecycle():
        docker_preflight()
        old_mask = os.umask(0o077)
        try:
            with tempfile.TemporaryDirectory(prefix="bravon-remote-", dir=identity["runner_temp"]) as temp_dir:
                scratch = Path(temp_dir)
                lab = docker_lab_factory(root=scratch / "disposable", slot=SLOT)
                started = False
                cleanup_error: Exception | None = None
                try:
                    lab.start()
                    started = True
                    raw = scratch / "controller-private.json"
                    report = run_qualification(
                        lab,
                        repeats=1,
                        scenarios=chosen,
                        confirmation=RUN_CONFIRMATION,
                        output=raw,
                        # Never echo raw Docker exceptions, host paths or responses to CI logs.
                        on_progress=lambda _message: None,
                    )
                    ok, _reason = verify_report(raw)
                    if not ok:
                        raise ValueError("Controller report failed offline integrity verification")
                    minimal = build_minimal_receipt(report, requested=chosen, identity=identity)
                finally:
                    # No non-disposable Docker resource is touched.
                    if started or lab.record_file.exists():
                        try:
                            lab.stop()
                        except Exception as exc:
                            cleanup_error = exc
                if cleanup_error is not None:
                    raise ValueError("Disposable Docker cleanup could not be verified")
                write_private_receipt(destination, minimal)
        finally:
            os.umask(old_mask)
        return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Private, owner-approved GH-hosted Docker qualification")
    parser.add_argument("--scenario", default="all", choices=("all", *SCENARIOS))
    parser.add_argument("--confirm", default="")
    parser.add_argument("--plan", action="store_true", help="Print bounded plan; never access Docker")
    args = parser.parse_args(argv)
    try:
        scenarios = selected_scenarios(args.scenario)
        if args.plan:
            print(json.dumps({
                "execution": False,
                "scenarios": scenarios,
                "model_calls": 0,
                "remote_runner": "GitHub Actions workflow_dispatch only",
                "required_confirmation": CONSENT,
                "networks": "private fixed disposable lab networks only",
                "artifact": "privacy-minimized receipt, not raw controller logs",
            }, indent=2))
            return 0
        destination = execute(args.scenario, confirmation=args.confirm, environ=os.environ)
    except (ValueError, OSError, TypeError, KeyError, RemoteCancellation) as exc:
        # Never print raw Docker/stdout/stderr, private environment or model data.
        print("REMOTE QUALIFICATION REFUSED: " + type(exc).__name__, file=sys.stderr)
        return 2
    print("Remote disposable qualification completed; private minimized receipt generated.")
    print("No hosted model requests were made. Controller evidence is self-digested, not attested.")
    print("Private artifact was written in the ephemeral runner directory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
