"""Safety and lifecycle tests of two-system Antibody transfer.

All Docker commands go into the existing FakeDockerRunner. This test suite
does NOT run Docker Desktop or make any Meta API requests.
"""
from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest
from proofops import immortality_docker

from proofops.immortality import digest, valid_transfer_digest
from proofops.immortality_docker import CONSENT, main, run_transfer
from proofops.model_protocol import WireInvestigator
from proofops.real_lab import CONFIRM_PHRASE
from test_hosted_muse_matrix import _lab, _model
from test_real_lab import FakeDockerRunner


@pytest.fixture
def dns_recovery(monkeypatch, tmp_path):
    lab, runner = _lab(tmp_path)
    try:
        lab.start()
        lab.inject("dns-drift")
        provider, calls = _model(monkeypatch, "restore_dns")
        lab.investigate(agent=WireInvestigator(provider), label=provider.source_label)
        verified = lab.verify()
        finished = lab.repair(
            approved=True, expected_revision=verified["revision"],
            confirmation=CONFIRM_PHRASE,
        )
        assert len(calls) == 8
    finally:
        lab.stop()
    assert not runner.projects
    return finished


def test_two_system_transfer_blocks_danger_and_allows_safe_control(dns_recovery, tmp_path):
    runner = FakeDockerRunner()
    original = digest(dns_recovery)
    destination_root = tmp_path / "new-destination"
    result = run_transfer(dns_recovery, slot=150, root=destination_root, runner=runner)
    assert result["mode"] == "SIMULATED_DOCKER_TEST"
    assert result["status"] == "verified-experimental-transfer"
    assert result["destination"]["slot"] == 150
    assert [x["policy_decision"] for x in result["cases"]] == ["BLOCK", "ALLOW"]
    assert all(x["expected_effect_observed"] for x in result["cases"])
    assert result["cases"][0]["clone_after"] != result["cases"][1]["clone_after"]
    assert {
        x["id"] for x in result["cases"][0]["clone_after"] if not x["passed"]
    } == {"dns-record", "e2e"}
    assert all(x["passed"] for x in result["cases"][1]["clone_after"])
    assert all(x["passed"] for x in result["cases"][0]["clone_before"])
    assert result["active_destination_remained_healthy"] is True
    assert result["cleanup_ok"] is True
    assert valid_transfer_digest(result)
    assert not destination_root.exists()
    assert not runner.projects
    assert digest(dns_recovery) == original, "Source A must be immutable"
    # The fake source model is never called during destination simulation.
    assert not any("repair" in args or "inject" in args for _, args in runner.calls)
    # Active B must not receive a wrong DNS command; only the verification clone
    # should see the temporary changes inside its own generated compose project.
    assert all(name.startswith(("proofops-a-", "proofops-v-")) for name, _ in runner.calls)


def test_unsafe_transfer_does_not_claim_success_if_clone_fails(dns_recovery, tmp_path):
    runner = FakeDockerRunner()
    runner.fail_sandbox_up = True
    root = tmp_path / "failed-clone"
    result = run_transfer(dns_recovery, slot=150, root=root, runner=runner)
    assert result["status"] == "failed"
    assert result["cleanup_ok"] is True
    assert result.get("error_class") == "DockerLabError"
    assert not result["active_destination_remained_healthy"]
    assert valid_transfer_digest(result)
    assert not root.exists()
    assert not runner.projects


@pytest.mark.parametrize("slot", [120, 121])
def test_cannot_reuse_source_network(dns_recovery, tmp_path, slot):
    runner = FakeDockerRunner()
    root = tmp_path / "never-created"
    with pytest.raises(ValueError):
        run_transfer(dns_recovery, slot=slot, root=root, runner=runner)
    assert not root.exists()
    assert not runner.calls


def test_reused_destination_directory_is_rejected(dns_recovery, tmp_path):
    runner = FakeDockerRunner()
    existing = tmp_path / "already-exists"
    existing.mkdir()
    with pytest.raises(ValueError, match="fresh private"):
        run_transfer(dns_recovery, slot=150, root=existing, runner=runner)
    assert not runner.calls


def test_cannot_run_without_explicit_docker_consent(dns_recovery, tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps(dns_recovery))
    output = tmp_path / "result.json"
    with pytest.raises(SystemExit):
        main(["--source-report", str(source), "--output", str(output)])
    assert not output.exists()


def test_tampered_source_fails_before_any_docker_work(dns_recovery, tmp_path):
    altered = deepcopy(dns_recovery)
    altered["active_incident"]["proof"]["proof_digest"] = "0" * 64
    source = tmp_path / "tampered.json"
    source.write_text(json.dumps(altered))
    output = tmp_path / "refused.json"
    assert main(["--source-report", str(source), "--output", str(output),
                 "--confirm", CONSENT]) == 2
    assert not output.exists()
    assert not list(tmp_path.glob("antibody-lab-*"))


def test_no_external_ip_or_original_model_text_in_generated_report(dns_recovery, tmp_path):
    runner = FakeDockerRunner()
    result = run_transfer(dns_recovery, slot=150, root=tmp_path / "fresh", runner=runner)
    raw = json.dumps(result)
    assert "10.223.120." not in raw
    assert "10.223.150." not in raw
    assert "Fixture-only fault hypothesis" not in raw
    assert "fake-fixture-only" not in raw
    assert "model_inference_performed" in raw
    assert all(x["model_inference_performed"] is False for x in result["cases"])


def test_docker_preflight_refuses_missing_cli(monkeypatch):
    monkeypatch.setattr(immortality_docker.shutil, "which", lambda _name: None)
    with pytest.raises(immortality_docker.DockerLabError, match="Docker CLI unavailable"):
        immortality_docker._docker_engine_preflight()


def test_docker_preflight_refuses_stopped_daemon(monkeypatch):
    seen = []
    monkeypatch.setattr(immortality_docker.shutil, "which", lambda _name: "/usr/local/bin/docker")

    def stopped(cmd, **kwargs):
        seen.append((cmd, kwargs))
        return SimpleNamespace(returncode=1, stdout="", stderr="socket unavailable")

    monkeypatch.setattr(immortality_docker.subprocess, "run", stopped)
    with pytest.raises(immortality_docker.DockerLabError, match="daemon is not running"):
        immortality_docker._docker_engine_preflight()
    assert seen[0][0] == ["/usr/local/bin/docker", "info", "--format", "{{.ServerVersion}}"]
    assert seen[0][1]["timeout"] == 12


def test_docker_preflight_accepts_healthy_engine(monkeypatch):
    monkeypatch.setattr(immortality_docker.shutil, "which", lambda _name: "/usr/local/bin/docker")
    monkeypatch.setattr(
        immortality_docker.subprocess, "run",
        lambda _argv, **_kwargs: SimpleNamespace(returncode=0, stdout="29.5.3\n", stderr=""),
    )
    immortality_docker._docker_engine_preflight()


def test_stopped_daemon_blocks_before_creating_report_or_lab(monkeypatch, tmp_path, dns_recovery, capsys):
    source = tmp_path / "recovered.json"
    source.write_text(json.dumps(dns_recovery))
    report = tmp_path / "new-transfer.json"

    def failed_preflight():
        raise immortality_docker.DockerLabError("Docker Desktop daemon is not running")

    monkeypatch.setattr(immortality_docker, "_docker_engine_preflight", failed_preflight)
    result = main([
        "--source-report", str(source),
        "--output", str(report), "--slot", "150",
        "--confirm", CONSENT,
    ])
    assert result == 2
    assert "DOCKER PREFLIGHT BLOCKED" in capsys.readouterr().err
    assert not report.exists()
    assert not list(tmp_path.glob("antibody-lab-*"))
