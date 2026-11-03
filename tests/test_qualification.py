"""Qualification runner tests use a fake Compose runner, never host Docker."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from proofops.qualification import (
    RUN_CONFIRMATION, _digest, html_report, main, run_qualification, verify_report,
)
from proofops.real_lab import DockerLab, LabConflict
from test_real_lab import FakeDockerRunner


@pytest.fixture
def ready(tmp_path):
    runner = FakeDockerRunner()
    lab = DockerLab(root=tmp_path / "lab", runner=runner, slot=120)
    lab.start()
    return lab, runner


def test_all_three_faults_generate_qualified_proof(ready, tmp_path):
    lab, runner = ready
    target = tmp_path / "reports" / "result.json"
    report = run_qualification(lab, confirmation=RUN_CONFIRMATION, output=target)
    assert report["summary"]["passed"] == 3
    assert report["summary"]["failed"] == 0
    assert report["summary"]["complete"] is True
    assert report["runner_provenance"] == "injected-test-runner"
    assert report["model_used"] is False
    assert all(run["reset_to_healthy"] for run in report["runs"])
    assert all(run["unapproved_repair_denied"] for run in report["runs"])
    assert all(run["stale_revision_repair_denied"] for run in report["runs"])
    assert [run["proposed_action"] for run in report["runs"]] == [
        "restore_dns", "restore_proxy", "failover",
    ]
    assert lab.status()["service_status"] == "healthy"
    assert lab.status()["active_incident"] is None
    assert len(lab.status()["history"]) == 3
    assert not any(project.startswith("proofops-v-") for project in runner.projects)
    assert verify_report(target) == (True, "3/3 evidence runs internally consistent")
    assert "QUALIFIED" in html_report(report)
    assert "No AI model was used" in html_report(report)
    lab.stop()


def test_two_repeats_and_selection(ready, tmp_path):
    lab, _ = ready
    report = run_qualification(lab, repeats=2, scenarios=["backend-outage", "dns-drift"],
                               confirmation=RUN_CONFIRMATION, output=tmp_path / "runs.json")
    assert report["summary"]["passed"] == 4
    assert report["summary"]["planned_total"] == 4
    assert len(lab.status()["history"]) == 4
    lab.stop()


def test_refuses_missing_confirmation_before_docker_mutation(ready):
    lab, runner = ready
    prior = list(runner.calls)
    with pytest.raises(ValueError, match="confirmation"):
        run_qualification(lab)
    assert runner.calls == prior
    lab.stop()


def test_refuses_unresolved_incident_and_unsafe_inputs(ready):
    lab, runner = ready
    lab.inject("dns-drift")
    prior = list(runner.calls)
    with pytest.raises(LabConflict, match="unresolved incident"):
        run_qualification(lab, confirmation=RUN_CONFIRMATION)
    with pytest.raises(ValueError, match="Repeats"):
        run_qualification(lab, repeats=99, confirmation=RUN_CONFIRMATION)
    with pytest.raises(ValueError, match="known scenarios"):
        run_qualification(lab, scenarios=["outside-container"], confirmation=RUN_CONFIRMATION)
    assert all(args[0] == "exec" for _, args in runner.calls[len(prior):])
    lab.reset(); lab.stop()


def test_aborts_after_failed_sandbox_and_attempts_reset(ready, tmp_path):
    lab, runner = ready
    runner.fail_sandbox_up = True
    path = tmp_path / "partial.json"
    report = run_qualification(lab, confirmation=RUN_CONFIRMATION, output=path)
    assert report["summary"]["failed"] == 1
    assert report["summary"]["total"] == 1
    assert report["summary"]["complete"] is False
    assert report["runs"][0]["reset_to_healthy"] is True
    assert "DockerLabError" in report["runs"][0]["error"]
    assert lab.status()["service_status"] == "healthy"
    assert not any(project.startswith("proofops-v-") for project in runner.projects)
    assert verify_report(path)[0] is True  # Integrity-valid failure report, NOT qualified.
    lab.stop()


def test_refuses_overwriting_existing_file_before_docker_mutation(ready, tmp_path):
    lab, runner = ready
    p = tmp_path / "existing.json"
    p.write_text("keep me")
    before = list(runner.calls)
    with pytest.raises(FileExistsError):
        run_qualification(lab, confirmation=RUN_CONFIRMATION, output=p)
    assert p.read_text() == "keep me"
    assert runner.calls == before
    lab.stop()


def test_report_tampering_detected_even_when_outer_digest_recomputed(ready, tmp_path):
    lab, _ = ready
    path = tmp_path / "proof.json"
    run_qualification(lab, confirmation=RUN_CONFIRMATION, scenarios=["dns-drift"], output=path)
    data = json.loads(path.read_text())
    data["runs"][0]["recovery_proof"]["after"][0]["observed"] = "fabricated"
    data.pop("report_digest")
    data["report_digest"] = _digest(data)
    path.write_text(json.dumps(data))
    valid, reason = verify_report(path)
    assert valid is False
    assert "invariant" in reason or "digest" in reason
    lab.stop()


def test_report_invariants_survive_optimized_python(ready, tmp_path):
    lab, _ = ready
    path = tmp_path / "optimized-proof.json"
    run_qualification(lab, confirmation=RUN_CONFIRMATION, scenarios=["dns-drift"], output=path)
    data = json.loads(path.read_text())
    data["runs"][0]["unapproved_repair_denied"] = False
    data.pop("report_digest")
    data["report_digest"] = _digest(data)
    path.write_text(json.dumps(data))
    check = subprocess.run(
        [sys.executable, "-O", "-c",
         "from pathlib import Path; import sys; "
         "from proofops.qualification import verify_report; "
         "raise SystemExit(0 if not verify_report(Path(sys.argv[1]))[0] else 1)",
         str(path)],
        cwd=Path(__file__).parents[1], check=False,
    )
    assert check.returncode == 0
    lab.stop()


def test_dry_run_does_not_touch_docker(monkeypatch, capsys):
    class Explode:
        def __init__(self, *args, **kwargs):
            raise AssertionError("DockerLab should not be constructed in dry run")
    monkeypatch.setattr("proofops.qualification.DockerLab", Explode)
    assert main(["run", "--dry-run", "--repeats", "2"]) == 0
    assert '"will_change_disposable_docker_lab": false' in capsys.readouterr().out


def test_visual_report_escapes_project_name(ready):
    lab, _ = ready
    report = run_qualification(lab, confirmation=RUN_CONFIRMATION, scenarios=["dns-drift"])
    report["project"] = '<script>alert("x")</script>'
    html = html_report(report)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    lab.stop()


def test_model_credentials_are_not_forwarded_to_compose(monkeypatch, tmp_path):
    from proofops.real_lab import ComposeStack
    monkeypatch.setenv("MODEL_API_KEY", "test-secret-only")
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-only")
    monkeypatch.setenv("BASETEN_API_KEY", "test-secret-only")
    monkeypatch.setenv("SOME_SERVICE_TOKEN", "test-secret-only")
    stack = ComposeStack(tmp_path, "proofops-a-deadbeef12", 120, FakeDockerRunner())
    assert "MODEL_API_KEY" not in stack.env
    assert "OPENAI_API_KEY" not in stack.env
    assert "BASETEN_API_KEY" not in stack.env
    assert "SOME_SERVICE_TOKEN" not in stack.env
    assert "PATH" in stack.env


def test_ctrl_c_during_stale_check_resets_lab_and_writes_failed_report(ready, tmp_path, monkeypatch):
    """A single Ctrl+C during a slow health probe must not strand an injected fault."""
    lab, _ = ready
    original_status = lab.status
    armed = {"value": False, "occurred": False}
    progress_events = []

    def progress(message):
        progress_events.append(message)
        if "Testing denial of stale-revision repair" in message:
            armed["value"] = True

    def interrupted_status():
        if armed["value"]:
            armed["value"] = False
            armed["occurred"] = True
            raise KeyboardInterrupt()
        return original_status()

    monkeypatch.setattr(lab, "status", interrupted_status)
    output = tmp_path / "interrupted.json"
    report = run_qualification(lab, confirmation=RUN_CONFIRMATION,
                               output=output, on_progress=progress)
    assert armed["occurred"] is True
    assert report["summary"]["passed"] == 0
    assert report["summary"]["failed"] == 1
    assert report["summary"]["complete"] is False
    assert report["runs"][0]["interrupted"] is True
    assert report["runs"][0]["reset_to_healthy"] is True
    assert lab.status()["service_status"] == "healthy"
    assert lab.status()["active_incident"] is None
    assert output.exists()
    assert verify_report(output)[0] is True
    assert any("Resetting disposable lab" in line for line in progress_events)
    lab.stop()


def test_negative_checks_reuse_verified_before_snapshot(ready, monkeypatch):
    """Both safety refusals still use actual probes after rejection."""
    lab, _ = ready
    lab.inject("dns-drift")
    lab.analyze()
    verified = lab.verify()
    from proofops.qualification import _attempt_denied_repair
    original_status = lab.status
    calls = {"value": 0}

    def tracked_status():
        calls["value"] += 1
        return original_status()

    monkeypatch.setattr(lab, "status", tracked_status)
    revision = verified["revision"]
    assert _attempt_denied_repair(lab, approved=False, revision=revision, before=verified)
    assert _attempt_denied_repair(lab, approved=True, revision=revision - 1, before=verified)
    assert calls["value"] == 2  # One real post-check per rejected action.
    lab.reset()
    lab.stop()
