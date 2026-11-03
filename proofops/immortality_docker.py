"""Human-approved, isolated antibody transfer: old source is never touched.

Only a fresh, disposable internal DockerLab B is created. Dangerous changes
are staged in B's own verification clone, never in B's active services.
No hosted inference, generic shell execution, external workloads or auto repair.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
from typing import Any

from .immortality import (TRANSFER_SCHEMA, compile_antibody, digest, evaluate,
                          nightmare_plan, preview, topology_for_slot,
                          valid_transfer_digest, write_private)
from .real_lab import CommandRunner, DockerLab, DockerLabError

CONSENT = "RUN ISOLATED ANTIBODY LAB"
REQUIRED_CHECKS = frozenset({"dns-record", "proxy-route", "upstream-health", "e2e", "standby"})


def _checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"id": c["id"], "passed": c["passed"] is True} for c in checks]


def _healthy(checks: list[dict[str, Any]]) -> bool:
    return (isinstance(checks, list) and len(checks) == 5 and
            {c.get("id") for c in checks} == REQUIRED_CHECKS and
            all(c.get("passed") is True for c in checks))


def _one_clone_experiment(lab: DockerLab, state: dict[str, Any],
                          *, dangerous: bool) -> dict[str, Any]:
    """Only perform generated known commands within the new verification clone."""
    clone = lab._stack(state, verification=True)
    clone.init_files(lab.initial_config())
    attempted = False
    try:
        attempted = True
        clone.run("up", "-d", "--build", timeout=240)
        first = lab._wait(clone, _healthy)
        if not _healthy(first):
            raise DockerLabError("Isolated clone did not reach 5/5 baseline")
        if dangerous:
            clone.set_dns("wrong")
            second = lab._wait(
                clone,
                lambda c: {x["id"] for x in c if not x["passed"]} ==
                {"dns-record", "e2e"},
            )
            success = ({x["id"] for x in second if not x["passed"]} ==
                       {"dns-record", "e2e"})
        else:
            # A nontrivial control: select a different healthy backend.
            clone.set_proxy("backend-b")
            second = lab._wait(clone, _healthy)
            success = _healthy(second)
        if not success:
            raise DockerLabError("Clone observations contradicted the planned result")
        return {"case": "dangerous-change" if dangerous else "legitimate-control",
                "clone_before": _checks(first), "clone_after": _checks(second),
                "observed": True, "expected_effect_observed": True}
    finally:
        if attempted:
            removed = clone.run("down", "--remove-orphans", timeout=90, strict=False)
            if removed.code:
                raise DockerLabError("Clone cleanup failed; inspect the isolated lab")


def run_transfer(recovery: dict[str, Any], *, slot: int, root: Path,
                 runner: CommandRunner | None = None) -> dict[str, Any]:
    """One bounded transfer experiment. A runner override is for offline tests.

    Providing a fake runner always labels results as simulated, not real Docker.
    """
    initial = preview(recovery, destination_slot=slot)
    antibody = initial["antibody"]
    if antibody["family"] != "dns-gateway-binding":
        raise ValueError("Real Docker transfer is DNS-only for this milestone")
    if root.exists() or root.is_symlink() or not root.parent.is_dir():
        raise ValueError("Isolated run directory must be a fresh private path")
    if slot in (120, 121):
        raise ValueError("Existing source lab subnet reserved; choose a distinct slot")
    top = topology_for_slot(slot)
    plan = nightmare_plan(antibody, top)
    if [x["assessment"]["decision"] for x in plan] != ["BLOCK", "ALLOW"]:
        raise ValueError("Policy did not block dangerous and allow safe candidate")
    root.mkdir(mode=0o700)
    lab = DockerLab(root=root, slot=slot, runner=runner)
    result: dict[str, Any] = {
        "schema": TRANSFER_SCHEMA,
        "mode": "SIMULATED_DOCKER_TEST" if runner is not None else "REAL_ISOLATED_DOCKER",
        "status": "incomplete",
        "antibody": antibody,
        "destination": {"system": "B", "slot": slot, "different_from_source": True},
        "cases": [],
        "active_destination_remained_healthy": False,
        "cleanup_ok": False,
        "limitations": ("Controller-generated origin proof is not independently signed. "
                        "One DNS invariant is not universal system immunity."),
    }
    started = False
    cleanup_error = None
    try:
        before = lab.start()
        started = True
        if before.get("service_status") != "healthy" or not _healthy(before.get("checks", [])):
            raise DockerLabError("Destination B failed original baseline probes")
        stable_fingerprint = before["fingerprint"]
        state = lab._state()
        b = lab._stack(state)
        if b.edge_ip != top["gateway_ip"]:
            raise DockerLabError("Generated topology differs from real Docker")
        candidates = [
            {"dns_answer_ip": b.wrong_ip, "upstream_ip": b.backend_a_ip},
            {"dns_answer_ip": b.edge_ip, "upstream_ip": b.backend_b_ip},
        ]
        for i, danger in enumerate((True, False)):
            expected = "BLOCK" if danger else "ALLOW"
            assessment = evaluate(antibody, top, candidates[i])
            if (assessment["decision"] != expected or
                    assessment["decision"] != plan[i]["expected"]):
                raise DockerLabError("Policy/physical candidate mismatch")
            observed = _one_clone_experiment(lab, state, dangerous=danger)
            observed["policy_decision"] = assessment["decision"]
            observed["model_inference_performed"] = False
            result["cases"].append(observed)
            active_now = lab.status()
            if (active_now["service_status"] != "healthy" or
                    active_now["fingerprint"] != stable_fingerprint or
                    active_now.get("active_incident") is not None):
                raise DockerLabError("Active destination changed during an experiment")
        result["active_destination_remained_healthy"] = True
        result["status"] = "verified-experimental-transfer"
    except Exception as exc:
        result["status"] = "failed"
        result["error_class"] = type(exc).__name__  # avoid leaking Docker stderr
    finally:
        if started:
            try:
                lab.stop()  # only B's two generated Compose project names
            except Exception:
                cleanup_error = "destination-cleanup-failed"
        if cleanup_error is None:
            result["cleanup_ok"] = True
            shutil.rmtree(root)
        else:
            result["status"] = "failed"
            result["cleanup_ok"] = False
            result["error_class"] = cleanup_error
            # Preserve the private run directory if cleanup failed.
    if result["status"] != "verified-experimental-transfer" or not result["cleanup_ok"]:
        result["status"] = "failed"
    result["report_digest"] = digest(result)
    return result



def _docker_engine_preflight() -> None:
    """Read-only engine check; refuse before report creation or Docker mutation."""
    binary = shutil.which("docker")
    if binary is None:
        raise DockerLabError("Docker CLI unavailable; install Docker Desktop first")
    try:
        probe = subprocess.run(
            [binary, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=12, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        raise DockerLabError(
            "Docker Desktop engine unavailable; open Docker Desktop and confirm docker info works"
        ) from None
    if probe.returncode != 0 or not probe.stdout.strip():
        raise DockerLabError(
            "Docker Desktop daemon is not running; open Docker Desktop, then verify docker info"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Explicitly approved, isolated Docker antibody transfer (no Meta calls)"
    )
    parser.add_argument("--source-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--slot", type=int, default=150)
    parser.add_argument("--confirm", default="")
    args = parser.parse_args(argv)
    if args.confirm != CONSENT:
        parser.error("Operator must explicitly supply --confirm '" + CONSENT + "'")
    output = args.output.expanduser()
    if output.exists() or output.is_symlink() or not output.parent.is_dir() or output.parent.is_symlink():
        print("Refusing existing output or unsafe report directory", file=sys.stderr)
        return 2
    try:
        recovery = json.loads(args.source_report.expanduser().read_text(encoding="utf-8"))
        compile_antibody(recovery)
        preview(recovery, destination_slot=args.slot)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("Source recovery not eligible: " + str(exc)[:240], file=sys.stderr)
        return 2
    try:
        _docker_engine_preflight()
    except DockerLabError as exc:
        print("DOCKER PREFLIGHT BLOCKED: " + str(exc), file=sys.stderr)
        print("No System B Docker experiment ran; no report was created.", file=sys.stderr)
        return 2
    print("EXPLICIT DISPOSABLE DOCKER EXPERIMENT")
    print("System A recovery: READ ONLY; System B subnet slot:", args.slot)
    print("Dangerous change only affects B's verification clone.")
    print("No Meta requests, real customer workloads, or automatic repairs.")
    root = output.parent / ("antibody-lab-" + secrets.token_hex(8))
    old_umask = os.umask(0o077)
    try:
        result = run_transfer(recovery, slot=args.slot, root=root)
        write_private(output, result)
    except (ValueError, OSError, DockerLabError) as exc:
        print("Antibody experiment refused: " + str(exc)[:240], file=sys.stderr)
        return 2
    finally:
        os.umask(old_umask)
    if not valid_transfer_digest(result):
        print("Report digest mismatch", file=sys.stderr)
        return 3
    print("Mode:", result["mode"])
    print("Outcome:", result["status"])
    print("Cases:", [(x["case"], x["policy_decision"], x["expected_effect_observed"])
                    for x in result["cases"]])
    print("Active B unaffected:", result["active_destination_remained_healthy"])
    print("Temporary Docker stacks cleaned:", result["cleanup_ok"])
    print("Private report:", output)
    return 0 if result["status"] == "verified-experimental-transfer" else 3


if __name__ == "__main__":
    raise SystemExit(main())
