"""Unit tests exercise DockerLab with a Docker CLI simulator, NOT real containers.

This distinguishes verified controller logic from not-yet-executed Docker Desktop E2E.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

from proofops.real_lab import (
    ACTIONS, CONFIRM_PHRASE, CommandResult, CommandRunner, ComposeStack,
    DockerLab, DockerLabError, LabConflict,
)


class FakeDockerRunner(CommandRunner):
    def __init__(self):
        self.projects = {}
        self.calls = []
        self.fail_sandbox_up = False
        self.block_active_healthy_e2e = False

    def run(self, argv, env, cwd, timeout):
        assert argv[:2] == ["docker", "compose"]
        project = argv[argv.index("-p") + 1]
        args = argv[argv.index("-p") + 2:]
        self.calls.append((project, args))
        stack = Path(env["PROOFOPS_STACK_DIR"])
        prefix = env["PROOFOPS_DNS_IP"].rsplit(".", 1)[0]
        def result(code=0, stdout="", stderr=""):
            return CommandResult(code, stdout, stderr)
        op = args[0]
        if op == "up":
            if project.startswith("proofops-v-") and self.fail_sandbox_up:
                self.projects[project] = {"up": True, "backend-a": True}
                return result(1, stderr="Sandbox intentionally failed startup")
            self.projects[project] = {"up": True, "backend-a": True}
            return result()
        if op == "down":
            self.projects.pop(project, None)
            return result()
        if op == "start":
            self.projects[project][args[1]] = True
            return result()
        if op == "stop":
            self.projects[project][args[1]] = False
            return result()
        if op != "exec" or project not in self.projects:
            return result(1, stderr="Not running")
        command = args[3:]
        if command[:2] == ["nginx", "-T"]:
            return result(stdout=(stack / "nginx/default.conf").read_text())
        if command[:2] == ["nginx", "-t"] or command[:3] == ["nginx", "-s", "reload"]:
            return result()
        if command[:1] == ["nslookup"]:
            dns_file = (stack / "dns/hosts").read_text().split()
            return result(stdout=f"Server: {env['PROOFOPS_DNS_IP']}\nAddress: {env['PROOFOPS_DNS_IP']}:53\nName: {dns_file[1]}\nAddress: {dns_file[0]}\n")
        if command[:1] == ["wget"]:
            url = command[-1]
            parsed = urlparse(url)
            addr = parsed.hostname
            if addr == "app.proofops.test":
                dns_addr = (stack / "dns/hosts").read_text().split()[0]
                if dns_addr != env["PROOFOPS_EDGE_IP"]:
                    return result(4, stderr="Host resolves to unreachable IP")
                nginx_conf = (stack / "nginx/default.conf").read_text()
                addr = re.search(r"proxy_pass http://([\d.]+):8080;", nginx_conf).group(1)
            backend = {env["PROOFOPS_BACKEND_A_IP"]: "backend-a",
                       env["PROOFOPS_BACKEND_B_IP"]: "backend-b"}.get(addr)
            if not backend or (backend == "backend-a" and not self.projects[project]["backend-a"]):
                return result(4, stderr="unavailable")
            if parsed.hostname == "app.proofops.test" and project.startswith("proofops-a-") and self.block_active_healthy_e2e:
                return result(4, stderr="Forced post-apply HTTP regression")
            return result(stdout=json.dumps({"backend": backend, "status": "ok"}))
        return result(127, stderr=f"Unrecognized fake command {command}")


@pytest.fixture
def lab(tmp_path):
    runner = FakeDockerRunner()
    obj = DockerLab(root=tmp_path / ".proofops-runtime", runner=runner, slot=120)
    return obj, runner


def test_stack_ips_and_compose_guards(tmp_path):
    stack = ComposeStack(tmp_path, "proofops-a-deadbeef12", 120, FakeDockerRunner())
    assert stack.edge_ip == "10.223.120.10"
    assert stack.backend_b_ip == "10.223.120.22"
    assert stack.env["PROOFOPS_SUBNET"] == "10.223.120.0/24"
    with pytest.raises(ValueError):
        ComposeStack(tmp_path, "other-project", 120, FakeDockerRunner())
    with pytest.raises(ValueError):
        DockerLab(root=tmp_path, slot=220)
    compose = stack.compose_file.read_text()
    assert "internal: true" in compose
    assert "ports:" not in compose
    assert "/var/run/docker.sock" not in compose
    assert "read_only: true" in compose


def test_start_observes_real_probe_protocol_and_stop(lab):
    obj, runner = lab
    state = obj.start()
    assert state["lab_type"] == "real-docker"
    assert state["live_infrastructure"] is True
    assert state["service_status"] == "healthy"
    assert len(state["checks"]) == 5
    assert all(item["passed"] for item in state["checks"])
    assert all(project.startswith("proofops-") for project, _ in runner.calls)
    assert obj.stop()["status"] == "stopped"
    assert not runner.projects
    assert not obj.record_file.exists()


@pytest.mark.parametrize("scenario,action", [
    ("dns-drift", "restore_dns"),
    ("proxy-misroute", "restore_proxy"),
    ("backend-outage", "failover"),
])
def test_physical_fault_isolation_approval_and_recovery(lab, scenario, action):
    obj, runner = lab
    obj.start()
    damaged = obj.inject(scenario)
    i = damaged["active_incident"]
    assert damaged["service_status"] == "critical"
    assert not next(c["passed"] for c in damaged["checks"] if c["id"] == "e2e")
    with pytest.raises(LabConflict):
        obj.inject("dns-drift")
    diagnosed = obj.analyze()
    assert diagnosed["active_incident"]["action"] == action
    assert "not Meta" in diagnosed["active_incident"]["diagnostic_source"]
    verification = obj.verify()
    detail = verification["active_incident"]["verification"]
    assert detail["success"] is True
    assert all(c["passed"] for c in detail["sandbox_after"])
    assert {c["id"] for c in detail["sandbox_before"] if not c["passed"]} == \
           {c["id"] for c in damaged["checks"] if not c["passed"]}
    assert verification["service_status"] == "critical", "Sandbox must not repair active stack"
    assert not any(p.startswith("proofops-v-") for p in runner.projects), "Sandbox should be removed"
    with pytest.raises(LabConflict, match="approval"):
        obj.repair(approved=False, expected_revision=verification["revision"],
                   confirmation=CONFIRM_PHRASE)
    with pytest.raises(LabConflict, match="Stale"):
        obj.repair(approved=True, expected_revision=0, confirmation=CONFIRM_PHRASE)
    with pytest.raises(LabConflict, match="confirmation"):
        obj.repair(approved=True, expected_revision=verification["revision"], confirmation="YES")
    recovered = obj.repair(approved=True, expected_revision=verification["revision"],
                           confirmation=CONFIRM_PHRASE)
    assert recovered["service_status"] == "healthy"
    assert recovered["active_incident"]["status"] == "recovered"
    proof = recovered["active_incident"]["proof"]
    assert len(proof["proof_digest"]) == 64
    assert proof["result"] == "observed-recovery-in-disposable-docker-lab"
    assert len(recovered["history"]) == 1
    obj.stop()


def test_invalid_scenario_and_unverified_repair(lab):
    obj, _ = lab
    obj.start()
    with pytest.raises(ValueError):
        obj.inject("delete-everything")
    damaged = obj.inject("dns-drift")
    with pytest.raises(LabConflict, match="verification"):
        obj.repair(approved=True, expected_revision=damaged["revision"],
                   confirmation=CONFIRM_PHRASE)
    obj.stop()


def test_operator_drift_rejected_and_no_apply(lab):
    obj, runner = lab
    obj.start(); obj.inject("dns-drift"); obj.analyze()
    verified = obj.verify()
    stack = obj._stack(obj._state())
    (stack.stack_dir / "dns/hosts").write_text("10.223.120.48 app.proofops.test\n")
    with pytest.raises(LabConflict, match="drift"):
        obj.repair(approved=True, expected_revision=verified["revision"], confirmation=CONFIRM_PHRASE)
    obj.reset()
    obj.stop()


def test_failed_sandbox_start_attempts_cleanup(lab):
    obj, runner = lab
    obj.start(); obj.inject("dns-drift"); obj.analyze()
    runner.fail_sandbox_up = True
    with pytest.raises(DockerLabError, match="failed"):
        obj.verify()
    assert not any(p.startswith("proofops-v-") for p in runner.projects)
    obj.stop()


def test_reset_recovers_and_clears_active_incident(lab):
    obj, _ = lab
    obj.start(); obj.inject("backend-outage")
    recovered = obj.reset()
    assert recovered["service_status"] == "healthy"
    assert recovered["active_incident"] is None
    obj.stop()


def test_no_docker_command_when_no_start(lab):
    obj, runner = lab
    with pytest.raises(LabConflict, match="not been started"):
        obj.status()
    assert runner.calls == []


def test_no_api_secrets_or_prod_mounts():
    root = Path(__file__).resolve().parents[1]
    text = (root / "infra/compose.yaml").read_text()
    assert "MODEL_API_KEY" not in text
    assert "privileged:" not in text
    assert "network_mode: host" not in text
    assert "ports:" not in text
    assert "docker.sock" not in text
    assert set(ACTIONS) == {"restore_dns", "restore_proxy", "failover"}


def test_real_docker_api_is_disabled_by_default(monkeypatch):
    from fastapi.testclient import TestClient
    from proofops.api import create_app
    from proofops.core import IncidentLab
    monkeypatch.delenv("PROOFOPS_ENABLE_DOCKER_UI", raising=False)
    client = TestClient(create_app(IncidentLab()))
    assert client.get("/docker").status_code == 200
    assert "Real traffic" in client.get("/docker").text
    assert client.get("/assets/docker.js").status_code == 200
    assert client.get("/api/docker/status").json()["enabled"] is False
    response = client.post("/api/docker/start", json={"confirmation": "START LOCAL DOCKER LAB"},
                           headers={"X-ProofOps-Local-Intent": "proofops-local-console"})
    assert response.status_code == 403


def test_real_docker_api_blocks_cross_origin_without_intent(lab):
    from fastapi.testclient import TestClient
    from proofops.api import create_app
    from proofops.core import IncidentLab
    obj, runner = lab
    client = TestClient(create_app(IncidentLab(), docker_lab=obj))
    payload = {"confirmation": "START LOCAL DOCKER LAB"}
    no_header = client.post("/api/docker/start", json=payload)
    assert no_header.status_code == 403
    cross = client.post("/api/docker/start", json=payload, headers={
        "X-ProofOps-Local-Intent": "proofops-local-console", "Origin": "https://attacker.example"
    })
    assert cross.status_code == 403
    assert runner.calls == []


def test_real_docker_api_full_cycle_mocked(lab):
    from fastapi.testclient import TestClient
    from proofops.api import create_app
    from proofops.core import IncidentLab
    obj, _ = lab
    client = TestClient(create_app(IncidentLab(), docker_lab=obj))
    h = {"X-ProofOps-Local-Intent": "proofops-local-console"}
    assert client.get("/api/docker/status").json()["initialized"] is False
    live = client.post("/api/docker/start", json={"confirmation":"START LOCAL DOCKER LAB"}, headers=h)
    assert live.status_code == 200
    damaged = client.post("/api/docker/inject/backend-outage", json={}, headers=h)
    assert damaged.status_code == 200
    assert damaged.json()["service_status"] == "critical"
    diagnosis = client.post("/api/docker/analyze", json={}, headers=h)
    assert diagnosis.json()["active_incident"]["action"] == "failover"
    verified = client.post("/api/docker/verify", json={}, headers=h)
    assert verified.status_code == 200
    revision = verified.json()["revision"]
    repaired = client.post("/api/docker/repair", json={"approved": True,
        "expected_revision": revision, "confirmation": CONFIRM_PHRASE}, headers=h)
    assert repaired.status_code == 200
    assert repaired.json()["service_status"] == "healthy"
    stopped = client.post("/api/docker/stop", json={"confirmation": "STOP LOCAL DOCKER LAB"}, headers=h)
    assert stopped.status_code == 200


def test_real_repair_regression_rolls_back(monkeypatch, lab):
    obj, runner = lab
    obj.start(); obj.inject("dns-drift"); obj.analyze()
    verified = obj.verify()
    runner.block_active_healthy_e2e = True
    # Test fast-fail after the first observed regression; production retries for 12 s.
    monkeypatch.setattr(obj, "_wait", lambda stack, predicate, duration=12.0: stack.inspect())
    with pytest.raises(DockerLabError, match="original lab configuration restored"):
        obj.repair(approved=True, expected_revision=verified["revision"],
                   confirmation=CONFIRM_PHRASE)
    state = obj._state()
    assert state["config"]["dns_target"] == "wrong"
    assert state["active_incident"]["status"] == "diagnosed"
    assert state["active_incident"]["verification"] is None
    assert "10.223.120.99" in (obj._stack(state).stack_dir / "dns/hosts").read_text()
    obj.stop()
