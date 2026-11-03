"""Repeatable recovery qualification for the opt-in disposable Docker lab.

No model inference, arbitrary commands, network requests, or host-side mutations
beyond the known DockerLab API. The operator must explicitly opt into controlled
fault injection and recovery. Do not run concurrently with the dashboard.

This module also verifies exported report digests offline. Digests detect accidental
edits, NOT a signature or proof against intentional report fabrication.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import secrets
import sys
from time import monotonic
from typing import Any, Callable, Iterable

from .real_lab import (
    ACTIONS, CONFIRM_PHRASE, SCENARIOS, CommandRunner, DockerLab,
    DockerLabError, LabConflict, _digest,
)

RUN_CONFIRMATION = "RUN LOCAL DOCKER QUALIFICATION"
EXPECTED_ACTIONS = {
    "dns-drift": "restore_dns",
    "proxy-misroute": "restore_proxy",
    "backend-outage": "failover",
}
REQUIRED_CHECKS = {"dns-record", "proxy-route", "upstream-health", "e2e", "standby"}
MAX_REPEATS = 10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _checkset(checks: list[dict[str, Any]]) -> bool:
    return {c.get("id") for c in checks} == REQUIRED_CHECKS and len(checks) == len(REQUIRED_CHECKS)


def _healthy(checks: list[dict[str, Any]]) -> bool:
    return _checkset(checks) and all(c.get("passed") is True for c in checks)


def _failing(checks: list[dict[str, Any]]) -> set[str]:
    return {c["id"] for c in checks if not c.get("passed")}


def _digest_valid(obj: dict[str, Any]) -> bool:
    candidate = dict(obj)
    value = candidate.pop("proof_digest", None)
    return isinstance(value, str) and len(value) == 64 and _digest(candidate) == value


def _safe_error(exc: Exception) -> str:
    # We never read credential files or print environment variables here.
    # Preserve a bounded, actionable error without dumping raw tool output.
    message = str(exc).replace("\r", " ").replace("\n", " ")
    return f"{type(exc).__name__}: {message[:400]}"


def _write_report(path: Path, report: dict[str, Any], *, overwrite: bool = False) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Refusing symlinked report paths")
    if path.exists() and not overwrite:
        raise FileExistsError(f"Report already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(report, indent=2, sort_keys=True) + "\n"
    temp = path.with_name(path.name + ".tmp-" + secrets.token_hex(6))
    try:
        temp.write_text(blob, encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _verify_run(run: dict[str, Any]) -> tuple[bool, str]:
    if run.get("status") != "passed":
        return False, "run was not marked passed"
    try:
        valid = all((
            run["scenario"] in EXPECTED_ACTIONS,
            run["expected_action"] == EXPECTED_ACTIONS[run["scenario"]],
            run["proposed_action"] == run["expected_action"],
            run["e2e_failed_before"] is True,
            run["sandbox_reproduced_failure"] is True,
            run["sandbox_healthy_after"] is True,
            run["active_remained_broken_during_verification"] is True,
            run["unapproved_repair_denied"] is True,
            run["stale_revision_repair_denied"] is True,
            run["recovered_healthy"] is True,
            run["verification_digest_valid"] is True,
            run["recovery_digest_valid"] is True,
            run["verification_digest"] == run["verification"]["proof_digest"],
            run["recovery_proof"]["verification_digest"] == run["verification_digest"],
            _digest_valid(run["verification"]),
            _digest_valid(run["recovery_proof"]),
            _healthy(run["verification"]["sandbox_after"]),
            _failing(run["verification"]["sandbox_before"]) == _failing(run["initial_failure_checks"]),
            not _healthy(run["initial_failure_checks"]),
            not next(c["passed"] for c in run["initial_failure_checks"] if c["id"] == "e2e"),
            _healthy(run["recovery_proof"]["after"]),
            _failing(run["recovery_proof"]["before"]) == _failing(run["initial_failure_checks"]),
            run["recovery_proof"]["action"] == run["expected_action"],
        ))
    except (KeyError, StopIteration, TypeError, ValueError):
        return False, "run invariant or evidence digest mismatch"
    if not valid:
        return False, "run invariant or evidence digest mismatch"
    return True, "verified"


def verify_report(path: Path) -> tuple[bool, str]:
    """Offline integrity/consistency verification; NOT cryptographic attestation."""
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
        report = dict(content)
        checksum = report.pop("report_digest", None)
        if not isinstance(checksum, str) or _digest(report) != checksum:
            return False, "report digest mismatch"
        if report.get("schema_version") != "proofops-qualification-v1":
            return False, "unsupported report schema"
        runs = report["runs"]
        if not isinstance(runs, list) or not runs:
            return False, "no evidence runs"
        counted_passes = 0
        for index, run in enumerate(runs, start=1):
            if run.get("status") == "passed":
                ok, reason = _verify_run(run)
                if not ok:
                    return False, f"run {index}: {reason}"
                counted_passes += 1
        summary = report["summary"]
        if summary["passed"] != counted_passes or summary["total"] != len(runs):
            return False, "summary counts inconsistent"
        if summary["failed"] != len(runs) - counted_passes:
            return False, "summary failure count inconsistent"
        if summary["complete"] != (len(runs) == summary["planned_total"] and summary["failed"] == 0):
            return False, "summary completeness inconsistent"
        if any(r.get("status") == "passed" and r.get("reset_to_healthy") is not True for r in runs):
            return False, "a passed run lacks a healthy final reset"
        if report.get("model_used") is not False:
            return False, "incorrect model-provenance declaration"
        return True, f"{counted_passes}/{len(runs)} evidence runs internally consistent"
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return False, _safe_error(exc)


def _attempt_denied_repair(lab: DockerLab, *, approved: bool, revision: int,
                           before: dict[str, Any] | None = None) -> bool:
    # The just-completed verification already contains a live status/fingerprint.
    # Reusing it avoids an entire redundant five-probe Docker inspection before
    # each negative test; the *post*-denial inspection remains mandatory.
    baseline = before if before is not None else lab.status()
    try:
        lab.repair(approved=approved, expected_revision=revision, confirmation=CONFIRM_PHRASE)
    except LabConflict:
        after = lab.status()
        return (after["fingerprint"] == baseline["fingerprint"] and
                after["revision"] == baseline["revision"] and
                after["service_status"] == "critical")
    return False


def _run_once(lab: DockerLab, scenario: str, iteration: int,
              on_progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    started = monotonic()

    def progress(step: str) -> None:
        if on_progress is not None:
            on_progress(f"[{scenario} / repeat {iteration}] {step}")
    run: dict[str, Any] = {
        "scenario": scenario, "iteration": iteration, "started_at": _now(),
        "status": "failed", "expected_action": EXPECTED_ACTIONS[scenario],
        "diagnosis_engine": "real-probe-rules (not Meta)",
    }
    try:
        progress("Checking active baseline")
        before = lab.status()
        if before["service_status"] != "healthy" or not _healthy(before["checks"]):
            raise LabConflict("Active Docker environment is not at a healthy baseline")
        progress("Injecting known fault into disposable active stack")
        damaged = lab.inject(scenario)
        incident = damaged["active_incident"]
        run["incident_id"] = incident["id"]
        run["initial_failure_checks"] = damaged["checks"]
        run["e2e_failed_before"] = (
            damaged["service_status"] == "critical" and
            next(c["passed"] is False for c in damaged["checks"] if c["id"] == "e2e")
        )
        if not run["e2e_failed_before"]:
            raise RuntimeError("The injected fault did not break the client-to-service path")

        progress("Diagnosing fault using deterministic real probes")
        diagnosed = lab.analyze()
        run["proposed_action"] = diagnosed["active_incident"]["action"]
        if run["proposed_action"] != EXPECTED_ACTIONS[scenario]:
            raise RuntimeError("Diagnostic rules proposed an unexpected action")

        progress("Starting independent sandbox reproduction and repair verification")
        verified = lab.verify()
        item = verified["active_incident"]
        evidence = item["verification"]
        run["verification"] = evidence
        run["verification_digest"] = evidence["proof_digest"]
        run["verification_digest_valid"] = _digest_valid(evidence)
        run["sandbox_reproduced_failure"] = (
            _failing(evidence["sandbox_before"]) == _failing(damaged["checks"]) and
            not _healthy(evidence["sandbox_before"]))
        run["sandbox_healthy_after"] = _healthy(evidence["sandbox_after"])
        run["active_remained_broken_during_verification"] = (
            verified["service_status"] == "critical" and
            not _healthy(verified["checks"]))
        if not (run["verification_digest_valid"] and run["sandbox_reproduced_failure"] and
                run["sandbox_healthy_after"] and run["active_remained_broken_during_verification"]):
            raise RuntimeError("Independent verification invariants were not met")

        revision = verified["revision"]
        progress("Testing denial of unapproved repair")
        run["unapproved_repair_denied"] = _attempt_denied_repair(
            lab, approved=False, revision=revision, before=verified)
        progress("Testing denial of stale-revision repair (rejection is expected)")
        run["stale_revision_repair_denied"] = _attempt_denied_repair(
            lab, approved=True, revision=revision - 1, before=verified)
        if not (run["unapproved_repair_denied"] and run["stale_revision_repair_denied"]):
            raise RuntimeError("A forbidden repair was not rejected without state change")

        progress("Applying approved repair and measuring actual recovery")
        recovered = lab.repair(approved=True, expected_revision=revision,
                               confirmation=CONFIRM_PHRASE)
        recovery = recovered["active_incident"]["proof"]
        run["recovery_proof"] = recovery
        run["recovery_digest_valid"] = _digest_valid(recovery)
        run["recovered_healthy"] = (recovered["service_status"] == "healthy" and
                                    _healthy(recovered["checks"]) and
                                    recovered["active_incident"]["status"] == "recovered")
        if not (run["recovery_digest_valid"] and run["recovered_healthy"]):
            raise RuntimeError("Post-apply recovery evidence is incomplete or unhealthy")
        if recovery["verification_digest"] != evidence["proof_digest"]:
            raise RuntimeError("Recovery proof does not link to verified sandbox proof")
        valid, why = _verify_run({**run, "status": "passed"})
        if not valid:
            raise RuntimeError(f"Qualification report failed internal validation: {why}")
        run["status"] = "passed"
        progress("Real service recovery and safety checks passed")
    except KeyboardInterrupt:
        # Ctrl+C is not an Exception subclass. Without this handler the entire
        # qualification exits immediately, leaving an injected fault and no
        # evidence report. The outer runner will attempt a baseline reset.
        run["interrupted"] = True
        run["error"] = "Operator interrupted this run (Ctrl+C)"
        progress("Interrupted: preparing a partial report and attempting baseline reset")
    except Exception as exc:
        run["error"] = _safe_error(exc)
        progress("Failure: " + run["error"])
    finally:
        run["duration_seconds"] = round(monotonic() - started, 3)
        run["finished_at"] = _now()
    return run


def run_qualification(lab: DockerLab, *, repeats: int = 1,
                      scenarios: Iterable[str] = tuple(SCENARIOS),
                      confirmation: str = "", output: Path | None = None,
                      on_progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Use only against a pre-started disposable lab; never calls start/stop.

    Any unexpected failure stops the series, attempts to reset the known lab,
    and is recorded as a failed run. It never silently claims a healthy lab.
    """
    if confirmation != RUN_CONFIRMATION:
        raise ValueError("Exact operator confirmation required before running destructive fault tests")
    if not 1 <= repeats <= MAX_REPEATS:
        raise ValueError(f"Repeats must be 1..{MAX_REPEATS}")
    chosen = list(scenarios)
    if not chosen or any(s not in SCENARIOS for s in chosen) or len(set(chosen)) != len(chosen):
        raise ValueError("Select one or more distinct known scenarios")
    if output is not None and (output.exists() or output.is_symlink()):
        raise FileExistsError(f"Refusing to overwrite existing qualification report: {output}")
    if on_progress is not None:
        on_progress("Checking existing disposable Docker lab and five baseline probes")
    initial = lab.status()
    active = initial.get("active_incident")
    if active and active["status"] != "recovered":
        raise LabConflict("An unresolved incident is active; resolve or reset it manually first")
    if initial["service_status"] != "healthy" or not _healthy(initial["checks"]):
        raise LabConflict("The real Docker environment must be fully healthy before qualification")

    report: dict[str, Any] = {
        "schema_version": "proofops-qualification-v1", "created_at": _now(),
        "project": initial["project"], "lab_type": "disposable-local-docker",
        "model_used": False, "diagnosis_provenance": "deterministic rules over real probes",
        "runner_provenance": ("docker-cli-subprocess" if type(lab.runner) is CommandRunner
                              else "injected-test-runner"),
        "notes": ["Run by an opt-in local operator against disposable containers only.",
                  "Hashes are integrity checks, not digital signatures or externally audited attestations.",
                  "No claim of Meta model inference or general autonomous diagnosis."],
        "planned_scenarios": chosen, "repeats": repeats, "runs": [],
    }
    abort = False
    benchmark_started = monotonic()
    for iteration in range(1, repeats + 1):
        for scenario in chosen:
            outcome = _run_once(lab, scenario, iteration, on_progress=on_progress)
            report["runs"].append(outcome)
            # Reset the known ProofOps environment to its baseline, but do NOT stop it.
            if on_progress is not None:
                on_progress(f"[{scenario} / repeat {iteration}] Resetting disposable lab to healthy baseline")
            try:
                reset = lab.reset()
                outcome["reset_to_healthy"] = reset["service_status"] == "healthy"
                if not outcome["reset_to_healthy"]:
                    outcome["status"] = "failed"
                    outcome["error"] = "Known baseline reset did not produce a healthy state"
            except KeyboardInterrupt:
                outcome["reset_to_healthy"] = False
                outcome["status"] = "failed"
                outcome["error"] = "Operator interrupted baseline reset; manually inspect the disposable lab"
                if on_progress is not None:
                    on_progress("WARNING: reset was interrupted; inspect lab state before another run")
            except Exception as exc:
                outcome["reset_to_healthy"] = False
                outcome["status"] = "failed"
                outcome["error"] = "Post-run reset failed: " + _safe_error(exc)
            if on_progress is not None:
                on_progress(f"[{scenario} / repeat {iteration}] Run status: {outcome['status']} "
                            f"(baseline reset: {outcome['reset_to_healthy']})")
            if outcome["status"] != "passed":
                abort = True
                break
        if abort:
            break
    passed = sum(run["status"] == "passed" for run in report["runs"])
    report["summary"] = {
        "passed": passed, "failed": len(report["runs"]) - passed,
        "total": len(report["runs"]),
        "planned_total": len(chosen) * repeats,
        "success_rate": round(passed / len(report["runs"]), 4) if report["runs"] else 0,
        "complete": not abort and len(report["runs"]) == len(chosen) * repeats,
        "total_seconds": round(monotonic() - benchmark_started, 3),
    }
    report["finished_at"] = _now()
    report["report_digest"] = _digest(report)
    if output is not None:
        _write_report(output, report)
    return report


def html_report(report: dict[str, Any]) -> str:
    """Pure offline report; values are escaped and no external scripts run."""
    s = report["summary"]
    rows = []
    for run in report["runs"]:
        passed = run.get("status") == "passed"
        icon = "PASS" if passed else "FAIL"
        rows.append("<tr>"
                    f"<td>{escape(run['scenario'])}</td>"
                    f"<td>{escape(str(run['iteration']))}</td>"
                    f"<td class={'ok' if passed else 'bad'}>{icon}</td>"
                    f"<td>{escape(str(run.get('proposed_action', '—')))}</td>"
                    f"<td>{escape(str(run.get('duration_seconds', '—')))} s</td>"
                    f"<td>{escape(str(run.get('verification_digest', '—'))[:14])}</td>"
                    "</tr>")
    result = "QUALIFIED" if s["complete"] and s["failed"] == 0 else "NOT QUALIFIED"
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ProofOps — Reliability Qualification</title>
<style>
:root{{--bg:#0b101b;--panel:#141c2b;--ink:#f1f5fa;--muted:#9dabbd;--line:#293344;--teal:#8af0c9;--red:#ff9da8}}
*{{box-sizing:border-box}}body{{font-family:ui-sans-serif,system-ui,-apple-system,sans-serif;margin:0;background:var(--bg);color:var(--ink);line-height:1.55}}
main{{max-width:1040px;margin:auto;padding:56px 24px}}.eyebrow{{color:var(--teal);font-size:12px;letter-spacing:.22em;font-weight:700}}
h1{{font-size:clamp(34px,5vw,58px);letter-spacing:-.055em;line-height:1.05;margin:16px 0}}p{{color:var(--muted)}}
.panels{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:30px 0}}
.panel{{border:1px solid var(--line);border-radius:18px;background:var(--panel);padding:24px}}
.value{{font-size:38px;font-weight:700;letter-spacing:-.04em}}.label{{color:var(--muted);font-size:13px}}
section{{padding-top:18px}}.tablebox{{overflow-x:auto;border:1px solid var(--line);border-radius:18px}}
table{{border-collapse:collapse;width:100%;min-width:660px}}th,td{{text-align:left;padding:17px;border-bottom:1px solid var(--line)}}
th{{font-size:12px;color:var(--muted);letter-spacing:.08em}}tr:last-child td{{border:0}}
.ok{{color:var(--teal);font-weight:700}}.bad{{color:var(--red);font-weight:700}}code{{font-size:12px;color:#b0c2dc}}
footer{{margin-top:36px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}}
@media(max-width:620px){{.panels{{grid-template-columns:1fr}}}}
</style></head><body><main>
<div class="eyebrow">PROOFOPS / LOCAL DOCKER LAB</div>
<h1>Reliability qualification</h1>
<p>Repeated, controlled failure and recovery evidence from an isolated Docker environment. No AI model was used.</p>
<div class="panels"><div class="panel"><div class="value">{s['passed']}/{s['total']}</div><div class="label">Successful recoveries</div></div>
<div class="panel"><div class="value">{s['total_seconds']}s</div><div class="label">Measured workflow time</div></div>
<div class="panel"><div class="value" style="font-size:24px;color:{'var(--teal)' if result == 'QUALIFIED' else 'var(--red)'}">{result}</div><div class="label">Overall qualification status</div></div></div>
<section><h2>Incident runs</h2><div class="tablebox"><table><thead><tr>
<th>Scenario</th><th>Iteration</th><th>Result</th><th>Proposed action</th><th>Duration</th><th>Verification hash</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>
<section><h2>Evidence contract</h2><p>Each passing run observed a failed real HTTP path, matched the failure in an isolated replica, verified an approved repair, rejected unapproved and stale requests, and ended with a healthy active service. JSON proof packets contain five individual probes before and after.</p></section>
<footer>Project: {escape(report['project'])} · Report checksum: <code>{escape(report['report_digest'])}</code>
<p>Checksums detect accidental modifications only. This is not a signed attestation, production certification, or AI capability benchmark.</p></footer></main></body></html>'''


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ProofOps no-key real Docker reliability qualification")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Explicitly run controlled faults on a started ProofOps Docker lab")
    run.add_argument("--confirm", default="", help=f'Exact value: {RUN_CONFIRMATION}')
    run.add_argument("--repeats", type=int, default=1)
    run.add_argument("--scenarios", nargs="+", choices=tuple(SCENARIOS), default=list(SCENARIOS))
    run.add_argument("--root", type=Path, default=Path.cwd() / ".proofops-runtime")
    run.add_argument("--slot", type=int, default=120)
    run.add_argument("--output", type=Path, default=None)
    run.add_argument("--dry-run", action="store_true", help="Print planned runs; do not invoke Docker")
    verify = sub.add_parser("verify-report", help="Verify an existing JSON report without Docker")
    verify.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    if args.command == "verify-report":
        ok, reason = verify_report(args.path)
        print(("PASS: " if ok else "FAIL: ") + reason)
        return 0 if ok else 1
    if args.dry_run:
        print(json.dumps({"will_change_disposable_docker_lab": False,
                          "scenarios": args.scenarios, "repeats": args.repeats,
                          "required_confirmation": RUN_CONFIRMATION}, indent=2))
        return 0
    filename = f"qualification-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(3)}.json"
    output = args.output or Path("reports") / filename
    try:
        if output.with_suffix(".html").exists() or output.with_suffix(".html").is_symlink():
            raise FileExistsError("Refusing to overwrite existing HTML report: " + str(output.with_suffix(".html")))
        result = run_qualification(DockerLab(root=args.root, slot=args.slot),
                                   repeats=args.repeats, scenarios=args.scenarios,
                                   confirmation=args.confirm, output=output,
                                   on_progress=lambda msg: print(msg, file=sys.stderr, flush=True))
        html_file = output.with_suffix(".html")
        html_file.write_text(html_report(result), encoding="utf-8")
        ok, message = verify_report(output)
        print(f"Completed: {result['summary']['passed']}/{result['summary']['total']} passing runs")
        print(f"JSON evidence: {output}")
        print(f"Local visual report: {html_file}")
        print(f"Offline evidence verification: {message}")
        return 0 if (ok and result["summary"]["complete"] and result["summary"]["failed"] == 0) else 1
    except KeyboardInterrupt:
        print("ProofOps qualification interrupted before a report could be finalized. "
              "Inspect the disposable lab with `python -m proofops.real_lab status` "
              "and use `python -m proofops.real_lab reset` if needed.", file=sys.stderr)
        return 130
    except (DockerLabError, ValueError, OSError) as exc:
        print("ProofOps qualification: " + _safe_error(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
