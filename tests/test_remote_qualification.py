"""Offline contract tests for the future owner-approved remote Docker runner.

These tests use only FakeDockerRunner. They do NOT start containers, dispatch
GitHub Actions, contact model providers, or establish physical proof.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os

import pytest

from proofops.qualification import RUN_CONFIRMATION, run_qualification, verify_report
from proofops.real_lab import DockerLab, _digest
from proofops.remote_qualification import (
    CONSENT, LIMITATIONS, SCENARIOS, SCHEMA, build_minimal_receipt,
    execute, main, require_explicit_runner, selected_scenarios,
    write_private_receipt, _require_known_fault, EXPECTED_FAULT_SIGNATURES,
)
from test_real_lab import FakeDockerRunner


@pytest.fixture
def identity(tmp_path):
    return {
        "run_id": "123456789", "attempt": "1", "sha": "a" * 40,
        "runner_temp": str(tmp_path),
    }


@pytest.fixture
def approved_env(tmp_path):
    return {
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": "S-h-u-b-h-1/bravon",
        "BRAVON_REMOTE_RUNNER_ENABLED": "YES",
        "GITHUB_ACTOR": "S-h-u-b-h-1",
        "GITHUB_TRIGGERING_ACTOR": "S-h-u-b-h-1",
        "DOCKER_HOST": "unix:///var/run/docker.sock",
        "GITHUB_RUN_ID": "123456789",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": "a" * 40,
        "RUNNER_TEMP": str(tmp_path),
    }


@pytest.fixture
def fake_report(tmp_path):
    """Generate a fully consistent *fake runner* report, not real Docker."""
    lab = DockerLab(root=tmp_path / "fake-runner", runner=FakeDockerRunner(), slot=191)
    try:
        lab.start()
        target = tmp_path / "fake.json"
        report = run_qualification(
            lab, repeats=1, scenarios=SCENARIOS,
            confirmation=RUN_CONFIRMATION, output=target,
        )
        assert verify_report(target)[0] is True
        assert report["runner_provenance"] == "injected-test-runner"
        return report
    finally:
        lab.stop()


def pretend_controller_report(report):
    """Only for unit-testing the small, PURE receipt renderer.

    Deliberately illustrates why changing a self-digested runner label
    is NOT third-party attestation and cannot be trusted as proof.
    """
    doc = deepcopy(report)
    doc["runner_provenance"] = "docker-cli-subprocess"
    doc["report_digest"] = _digest({k: v for k, v in doc.items() if k != "report_digest"})
    return doc


def test_three_fixed_scenarios_only():
    assert selected_scenarios("all") == SCENARIOS
    assert selected_scenarios("dns-drift") == ("dns-drift",)
    for candidate in ("all;curl", "shell", "", "dns-drift proxy-misroute"):
        with pytest.raises(ValueError, match="fixed Docker"):
            selected_scenarios(candidate)


def test_explicit_environment_gate_requires_private_owner_review(approved_env, tmp_path):
    assert require_explicit_runner(approved_env, CONSENT)["sha"] == "a" * 40
    for key, invalid in (
        ("GITHUB_ACTIONS", "false"),
        ("GITHUB_EVENT_NAME", "pull_request"),
        ("GITHUB_REF", "refs/heads/feature"),
        ("GITHUB_REPOSITORY", "evil/other"),
        ("BRAVON_REMOTE_RUNNER_ENABLED", ""),
        ("GITHUB_ACTOR", "another-user"),
        ("GITHUB_TRIGGERING_ACTOR", "another-user"),
        ("DOCKER_HOST", "tcp://external-daemon.example:2375"),
        ("DOCKER_HOST", ""),
        ("DOCKER_CONTEXT", "remote-cluster"),
        ("DOCKER_TLS_VERIFY", "1"),
        ("DOCKER_CERT_PATH", "/tmp/certs"),
        ("DOCKER_CONFIG", "/tmp/credential-cache"),
        ("GITHUB_RUN_ID", "not-a-number"),
        ("GITHUB_RUN_ATTEMPT", ""),
        ("GITHUB_SHA", "a" * 12),
        ("RUNNER_TEMP", ""),
    ):
        altered = dict(approved_env, **{key: invalid})
        with pytest.raises(ValueError):
            require_explicit_runner(altered, CONSENT)
    with pytest.raises(ValueError, match="confirmation"):
        require_explicit_runner(approved_env, "WRONG APPROVAL")


def test_refuse_unauthorized_before_docker_engine_probe(monkeypatch, approved_env, tmp_path):
    import proofops.remote_qualification as remote

    def forbidden():
        raise AssertionError("Docker preflight must never run")
    monkeypatch.setattr(remote, "docker_preflight", forbidden)
    incomplete = dict(approved_env)
    incomplete.pop("BRAVON_REMOTE_RUNNER_ENABLED")
    with pytest.raises(ValueError, match="Owner-enabled repository variable"):
        execute("dns-drift", confirmation=CONSENT, environ=incomplete)
    assert not (tmp_path / "bravon-remote-receipt.json").exists()


def test_fake_docker_source_cannot_be_presented_as_real(fake_report, identity):
    with pytest.raises(ValueError, match="fake-Docker"):
        build_minimal_receipt(fake_report, requested=SCENARIOS, identity=identity)


def test_minimal_receipt_contains_no_raw_probes_ips_or_paths(fake_report, identity):
    full = pretend_controller_report(fake_report)
    receipt = build_minimal_receipt(full, requested=SCENARIOS, identity=identity)
    assert receipt["schema"] == SCHEMA
    assert receipt["report_status"] == "QUALIFIED_CONTROLLER_REPORT"
    assert receipt["model_inference"] == "NONE_RULE_BASED_ONLY"
    assert receipt["execution_mode"] == "GH_HOSTED_DISPOSABLE_DOCKER"
    assert [r["scenario"] for r in receipt["results"]] == list(SCENARIOS)
    assert [r["action"] for r in receipt["results"]] == [
        "restore_dns", "restore_proxy", "failover",
    ]
    assert all(r["result"] == "PASSED" for r in receipt["results"])
    assert all(len(r["before"]) == 5 and len(r["sandbox_after"]) == 5
               and len(r["recovery_after"]) == 5 for r in receipt["results"])
    assert all(not all(check["passed"] for check in r["before"]) for r in receipt["results"])
    assert all(all(check["passed"] for check in r["sandbox_after"] + r["recovery_after"])
               for r in receipt["results"])
    assert receipt["limitations"] == LIMITATIONS
    assert _digest({k: v for k, v in receipt.items() if k != "content_digest"}) == receipt["content_digest"]
    raw = json.dumps(receipt)
    for forbidden in ("10.223.", "/tmp/", "MODEL_API_KEY", "OPENROUTER_API_KEY",
                      "hosted-muse", "secret-key", "container.stderr", "docker logs"):
        assert forbidden not in raw
    assert len(raw.encode()) < 10_000


def test_altered_full_report_cannot_be_relabelled_green(fake_report, identity):
    good = pretend_controller_report(fake_report)
    wrong = deepcopy(good)
    wrong["runs"][0]["verification"]["sandbox_after"][0]["passed"] = False
    wrong["report_digest"] = _digest({k: v for k, v in wrong.items() if k != "report_digest"})
    with pytest.raises(ValueError, match="observations"):
        build_minimal_receipt(wrong, requested=SCENARIOS, identity=identity)


@pytest.mark.parametrize("mutation", [
    lambda r: r["summary"].update({"failed": 1}),
    lambda r: r["summary"].update({"complete": False}),
    lambda r: r.update({"model_used": True}),
    lambda r: r.update({"repeats": 2}),
    lambda r: r["runs"].pop(),
    lambda r: r["runs"][0].update({"scenario": "unknown"}),
])
def test_failed_incomplete_or_mislabelled_report_is_refused(fake_report, identity, mutation):
    altered = pretend_controller_report(fake_report)
    mutation(altered)
    altered["report_digest"] = _digest({k: v for k, v in altered.items() if k != "report_digest"})
    with pytest.raises(ValueError):
        build_minimal_receipt(altered, requested=SCENARIOS, identity=identity)


def test_minimal_receipt_is_private_and_cannot_overwrite(tmp_path, identity, fake_report):
    doc = build_minimal_receipt(pretend_controller_report(fake_report),
                                requested=SCENARIOS, identity=identity)
    output = tmp_path / "receipt.json"
    write_private_receipt(output, doc)
    assert output.exists()
    assert output.stat().st_mode & 0o777 == 0o600
    assert json.loads(output.read_text())["content_digest"] == doc["content_digest"]
    with pytest.raises(ValueError, match="new"):
        write_private_receipt(output, doc)
    assert not (tmp_path / "other.json").exists()


def test_preview_plan_has_zero_side_effects(monkeypatch, capsys):
    import proofops.remote_qualification as remote

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Must never initialize real Docker in --plan mode")
    monkeypatch.setattr(remote, "docker_preflight", forbidden)
    monkeypatch.setattr(remote, "execute", forbidden)
    assert main(["--plan", "--scenario", "dns-drift"]) == 0
    text = capsys.readouterr().out
    assert '"execution": false' in text
    assert '"model_calls": 0' in text


def test_even_valid_fake_controller_cannot_write_remote_evidence(tmp_path, approved_env, monkeypatch):
    """No real Docker proof is forged from the fake runner in the test harness."""
    import proofops.remote_qualification as remote
    monkeypatch.setattr(remote, "docker_preflight", lambda: None)

    def fake_factory(*, root, slot):
        return DockerLab(root=root, slot=slot, runner=FakeDockerRunner())
    with pytest.raises(ValueError, match="fake-Docker"):
        execute("dns-drift", confirmation=CONSENT, environ=approved_env,
                docker_lab_factory=fake_factory)
    assert not (tmp_path / "bravon-remote-receipt.json").exists()


def test_manual_workflow_has_no_web_trigger_or_model_credentials():
    from pathlib import Path
    workflow = (Path(__file__).resolve().parents[1] /
                ".github" / "workflows" / "remote-docker-qualification.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "\n  push:" not in workflow
    assert "\n  pull_request:" not in workflow
    assert "environment: bravon-remote-docker-approval" not in workflow
    assert "github.actor == 'S-h-u-b-h-1'" in workflow
    assert "github.triggering_actor == 'S-h-u-b-h-1'" in workflow
    assert "BRAVON_REMOTE_RUNNER_ENABLED" in workflow
    assert "DOCKER_HOST: unix:///var/run/docker.sock" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "github.repository == 'S-h-u-b-h-1/bravon'" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "proofops.remote_qualification" in workflow
    assert "BRAVON_SCENARIO: ${{ inputs.scenario }}" in workflow
    assert '--scenario "$BRAVON_SCENARIO"' in workflow
    assert '--scenario "${{ inputs.scenario }}"' not in workflow
    assert "runner.temp }}/bravon-remote-receipt.json" in workflow
    assert "MODEL_API_KEY" not in workflow
    assert "OPENROUTER_API_KEY" not in workflow


def test_compose_limits_every_service_and_keeps_private_network():
    from pathlib import Path
    compose=(Path(__file__).resolve().parents[1] / "infra" / "compose.yaml").read_text()
    assert compose.count("    restart: \"no\"") == 5
    assert compose.count("    mem_limit: 256m") == 5
    assert compose.count("    cpus: 1.0") == 5
    assert compose.count("    pids_limit: 64") == 5
    assert "internal: true" in compose
    assert "\n    ports:" not in compose
    assert "/var/run/docker.sock" not in compose


@pytest.mark.parametrize("scenario,expected", [
    ("dns-drift", {"dns-record", "e2e"}),
    ("proxy-misroute", {"proxy-route", "upstream-health", "e2e"}),
    ("backend-outage", {"upstream-health", "e2e"}),
])
def test_only_exact_real_fault_signature_is_eligible(scenario,expected):
    probe_ids=("dns-record","proxy-route","upstream-health","e2e","standby")
    assert EXPECTED_FAULT_SIGNATURES[scenario] == expected
    valid=[{"id": name,"passed":name not in expected} for name in probe_ids]
    _require_known_fault(valid,scenario)
    for alternate in (set(), {"e2e"}, expected | {"standby"}):
        if alternate == expected:
            continue
        wrong=[{"id":name,"passed":name not in alternate} for name in probe_ids]
        with pytest.raises(ValueError,match="expected fixed fault signature"):
            _require_known_fault(wrong,scenario)
    with pytest.raises(ValueError,match="Unknown fault signature"):
        _require_known_fault(valid,"arbitrary-shell-command")


def test_disposable_images_are_immutable_digest_refs():
    from pathlib import Path
    import re
    root=Path(__file__).resolve().parents[1]
    compose=(root / "infra" / "compose.yaml").read_text(encoding="utf-8")
    images=re.findall(r"^\s*image:\s*([^\s#]+)",compose,re.MULTILINE)
    assert len(images)==3, "Expected CoreDNS, Nginx and probe images"
    assert "nginx:1.28-alpine" not in compose
    assert "image: nginx:1.30.6-alpine3.24@sha256:0e52bd054126cdc040b1276c0af347aeb02a41b9cfe305d6094767ac30e97949" in compose
    assert all(re.fullmatch(r"[a-z0-9./_-]+:[a-z0-9.-]+@sha256:[a-f0-9]{64}",img) for img in images)
    dockerfile=(root / "infra" / "backend" / "Dockerfile").read_text(encoding="utf-8")
    base=re.search(r"^FROM\s+([^\s#]+)",dockerfile,re.MULTILINE)
    assert base and re.fullmatch(r"python:3[.]12-alpine@sha256:[a-f0-9]{64}",base.group(1))


def test_ci_retains_full_pr_release_gate_without_running_benchmarks_on_every_commit():
    from pathlib import Path
    ci=(Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml").read_text()
    assert "types: [opened, synchronize, reopened, labeled, unlabeled]" in ci
    assert "full-release-check" in ci
    assert "github.event.pull_request.labels.*.name" in ci
    assert "fail-fast: false" in ci
    assert "cancel-in-progress:" in ci
    assert '["3.12"]' in ci
    assert '["3.10","3.12","3.13"]' in ci
    assert "python -m pytest -q" in ci
    assert "node --test tests/test_immortality_viewer.cjs" in ci
    assert "python qa/browser_smoke.py" in ci


def test_remote_preflight_refuses_missing_unix_socket_before_cli(monkeypatch):
    import proofops.remote_qualification as remote
    class MissingSocket:
        def is_socket(self):
            return False
    monkeypatch.setattr(remote,"LOCAL_DOCKER_SOCKET",MissingSocket())
    def forbidden(*args,**kwargs):
        raise AssertionError("CLI must not run if local Unix socket is missing")
    monkeypatch.setattr(remote.subprocess,"run",forbidden)
    with pytest.raises(ValueError,match="socket is missing"):
        remote.docker_preflight()


def test_remote_preflight_forces_unix_host_even_on_a_docker_enabled_runner(monkeypatch):
    import proofops.remote_qualification as remote
    class PresentSocket:
        def is_socket(self):
            return True
    monkeypatch.setattr(remote,"LOCAL_DOCKER_SOCKET",PresentSocket())
    captured=[]
    class Result:
        returncode=0
        stdout="27.1"
    def spy(argv,**kwargs):
        captured.append((argv,kwargs))
        return Result()
    monkeypatch.setattr(remote.subprocess,"run",spy)
    remote.docker_preflight()
    assert len(captured)==1
    assert captured[0][0]==[
        "docker","--host","unix:///var/run/docker.sock",
        "info","--format","{{.ServerVersion}}",
    ]
    assert captured[0][1]["timeout"] <= 15


@pytest.mark.parametrize("altered_value", ["", "alpha", "1"*4, None, 1])
def test_receipt_identity_rejects_missing_or_invalid_run_attempt(fake_report,identity,altered_value):
    full=pretend_controller_report(fake_report)
    changed=dict(identity,attempt=altered_value)
    with pytest.raises(ValueError,match="identity"):
        build_minimal_receipt(full,requested=SCENARIOS,identity=changed)


def test_receipt_rejects_unknown_or_partial_multi_scenario_selection(fake_report,identity):
    full=pretend_controller_report(fake_report)
    for chosen in ((),("dns-drift","backend-outage"),("backend-outage","dns-drift"),
                   ("dns-drift","shell"),("dns-drift","dns-drift")):
        with pytest.raises(ValueError,match="fixed scenario"):
            build_minimal_receipt(full,requested=chosen,identity=identity)


def test_offline_release_script_is_safe_bash_and_has_no_docker_or_network_side_effects():
    from pathlib import Path
    import subprocess
    script=(Path(__file__).resolve().parents[1]/"scripts"/"offline-release-check.sh")
    contents=script.read_text(encoding="utf-8")
    assert contents.startswith("#!/usr/bin/env bash")
    syntax=subprocess.run(["bash","-n",str(script)],capture_output=True,text=True,check=False)
    assert syntax.returncode == 0, syntax.stderr
    for forbidden in ("docker pull ","docker compose ","docker info ","pip install",
                      "curl ","wget ","workflow_dispatch --", "MODEL_API_KEY="):
        assert forbidden not in contents
    assert 'python -m proofops.remote_qualification' not in contents or "--plan" in contents
    assert "tests/test_remote_qualification.py" in contents
    assert "tests/test_remote_evidence.cjs" in contents


def test_interrupt_guard_restores_original_signal_handlers():
    import signal
    import proofops.remote_qualification as remote
    initial={s:signal.getsignal(s) for s in (signal.SIGTERM,signal.SIGINT)}
    with pytest.raises(remote.RemoteCancellation,match="Owner cancellation"):
        with remote._guarded_lifecycle():
            handler=signal.getsignal(signal.SIGTERM)
            assert callable(handler)
            handler(signal.SIGTERM,None)
    for s, old in initial.items():
        assert signal.getsignal(s) == old


def test_cancel_after_stack_start_attempts_cleanup_and_never_exports(
    tmp_path, approved_env, monkeypatch
):
    import proofops.remote_qualification as remote
    monkeypatch.setattr(remote,"docker_preflight",lambda:None)
    runner=FakeDockerRunner()

    def interrupted_factory(*, root, slot):
        lab=DockerLab(root=root,slot=slot,runner=runner)
        original_start=lab.start

        def start_then_interrupt():
            original_start()
            raise remote.RemoteCancellation("simulated owner cancellation")

        lab.start=start_then_interrupt
        return lab

    with pytest.raises(remote.RemoteCancellation):
        execute("dns-drift",confirmation=CONSENT,environ=approved_env,
                docker_lab_factory=interrupted_factory)
    assert runner.projects == {}, "all known disposable Compose projects should be removed"
    assert not (tmp_path/"bravon-remote-receipt.json").exists()


def test_signal_cancellation_has_no_green_status_in_main(monkeypatch,capsys):
    import proofops.remote_qualification as remote

    def abort(*_args,**_kwargs):
        raise remote.RemoteCancellation("simulated cancellation")

    monkeypatch.setattr(remote,"execute",abort)
    result=remote.main(["--scenario","dns-drift"])
    assert result == 2
    err=capsys.readouterr().err
    assert "REFUSED: RemoteCancellation" in err
    assert "simulated cancellation" not in err
