"""Provider-neutral, read-only investigation tests use FakeDockerRunner, not Docker."""
import pytest
from fastapi.testclient import TestClient

from proofops.investigation import (
    FinalStep, ToolStep, MAX_CALLS, RealReadOnlyTools, ReferenceInvestigator,
    investigate_readonly,
)
from proofops.real_lab import CONFIRM_PHRASE, CommandResult, DockerLab, LabConflict
from proofops.api import create_app
from proofops.core import IncidentLab
from test_real_lab import FakeDockerRunner


@pytest.fixture
def lab(tmp_path):
    runner = FakeDockerRunner()
    instance = DockerLab(root=tmp_path / "lab", runner=runner, slot=120)
    instance.start()
    yield instance, runner
    instance.stop()


@pytest.mark.parametrize("scenario,action", [
    ("dns-drift", "restore_dns"),
    ("proxy-misroute", "restore_proxy"),
    ("backend-outage", "failover"),
])
def test_investigator_then_independent_recovery(lab, scenario, action):
    instance, runner = lab
    instance.inject(scenario)
    calls_before = len(runner.calls)
    investigated = instance.investigate()
    incident = investigated["active_incident"]
    assert incident["action"] == action
    assert incident["status"] == "diagnosed"
    assert "NOT AI" in incident["diagnostic_source"]
    trace = incident["investigation"]
    assert trace["tool_calls"] == 6
    assert trace["read_only"] is True and trace["executed_repair"] is False
    assert len(trace["transcript"]) == 7
    assert all(entry["kind"] == "tool" for entry in trace["transcript"][:-1])
    during = runner.calls[calls_before:]
    assert during
    assert all(args[0] == "exec" for _, args in during)
    assert all(project.startswith("proofops-a-") for project, _ in during)
    verified = instance.verify()
    assert verified["active_incident"]["verification"]["success"] is True
    repaired = instance.repair(approved=True, expected_revision=verified["revision"],
                               confirmation=CONFIRM_PHRASE)
    assert repaired["service_status"] == "healthy"
    assert repaired["active_incident"]["status"] == "recovered"


def test_compound_fault_leads_to_abstain(lab):
    instance, _ = lab
    stack = instance._stack(instance._state())
    stack.set_dns("wrong")
    stack.set_proxy("bogus")
    result = investigate_readonly(RealReadOnlyTools(stack), ReferenceInvestigator(),
                                  label="local baseline")
    assert result["proposal"]["action"] == "none"
    assert "Multiple faults" in result["proposal"]["explanation"]


def test_healthy_path_leads_to_abstain(lab):
    instance, _ = lab
    stack = instance._stack(instance._state())
    result = investigate_readonly(RealReadOnlyTools(stack), ReferenceInvestigator(),
                                  label="local baseline")
    assert result["proposal"]["action"] == "none"


class UnknownToolAgent:
    def next_step(self, observations):
        return ToolStep("shell", {"cmd": "rm -rf /"})


class UncitedRepairAgent:
    def next_step(self, observations):
        return FinalStep("restore_dns", "Unknown", "No proof", ("invented",), 0.9)


class MissingCitationsAgent:
    def next_step(self, observations):
        return FinalStep("restore_dns", "Unknown", "No proof", (), 0.9)


class InvalidActionAgent:
    def next_step(self, observations):
        return FinalStep("exec", "Unknown", "No proof", (), 0.9)


@pytest.mark.parametrize("agent,error", [
    (UnknownToolAgent(), "allowlisted"),
    (UncitedRepairAgent(), "unobserved"),
    (MissingCitationsAgent(), "unobserved"),
    (InvalidActionAgent(), "allowed repair"),
])
def test_unsafe_agent_never_mutates_docker(lab, agent, error):
    instance, runner = lab
    stack = instance._stack(instance._state())
    before = len(runner.calls)
    with pytest.raises((LabConflict, ValueError), match=error):
        investigate_readonly(RealReadOnlyTools(stack), agent, label="untrusted-advice")
    assert runner.calls[before:] == []


def test_tool_argument_restrictions_and_budget(lab):
    instance, runner = lab
    stack = instance._stack(instance._state())
    tools = RealReadOnlyTools(stack)
    with pytest.raises(ValueError):
        tools.call("probe_backend", {"backend": "google.com"})
    with pytest.raises(ValueError):
        tools.call("lookup_dns", {"host": "elsewhere.test"})
    with pytest.raises(ValueError):
        tools.call("probe_backend", {"backend": "backend-a", "cmd": "sh"})
    assert len(tools.observations) == 0
    for _ in range(MAX_CALLS):
        tools.call("topology", {})
    with pytest.raises(LabConflict, match="budget"):
        tools.call("topology", {})


def test_investigation_requires_active_incident(lab):
    instance, runner = lab
    before = len(runner.calls)
    with pytest.raises(LabConflict, match="No unrecovered"):
        instance.investigate()
    assert runner.calls[before:] == []


def test_investigation_detects_drift_without_writing_proposal(lab):
    instance, runner = lab
    instance.inject("dns-drift")
    stack = instance._stack(instance._state())

    class MutatingAgent:
        def next_step(self, observations):
            stack.set_dns("edge")
            return FinalStep("none", "unknown", "abstain", (), 0.0)

    with pytest.raises(LabConflict, match="changed"):
        instance.investigate(agent=MutatingAgent())
    assert instance._state()["active_incident"]["status"] == "open"
    instance.reset()


def test_local_api_investigate_is_protected(lab, monkeypatch):
    instance, _ = lab
    client = TestClient(create_app(IncidentLab(), docker_lab=instance))
    instance.inject("dns-drift")
    assert client.post("/api/docker/investigate").status_code == 403
    result = client.post("/api/docker/investigate", headers={"X-ProofOps-Local-Intent":"proofops-local-console"})
    assert result.status_code == 200
    incident = result.json()["active_incident"]
    assert incident["investigation"]["proposal"]["action"] == "restore_dns"
    assert len(incident["investigation"]["transcript"]) == 7


def test_no_real_docker_commands_for_tool_actions(lab):
    instance, runner = lab
    stack = instance._stack(instance._state())
    tools = RealReadOnlyTools(stack)
    before = len(runner.calls)
    tools.call("lookup_dns", {})
    tools.call("inspect_gateway", {})
    tools.call("probe_backend", {"backend": "backend-b"})
    tools.call("customer_path", {})
    new = runner.calls[before:]
    assert all(args[0] == "exec" for _, args in new)
    assert all(args[3] in ("nslookup", "nginx", "wget") for _, args in new)


def test_reanalysis_invalidates_previous_verification(lab):
    instance, _ = lab
    instance.inject("dns-drift")
    instance.analyze()
    instance.verify()
    assert instance._state()["active_incident"]["verification"]
    state = instance.investigate()
    assert state["active_incident"]["verification"] is None
    with pytest.raises(LabConflict, match="verification"):
        instance.repair(approved=True, expected_revision=state["revision"], confirmation=CONFIRM_PHRASE)

class WrongButCitedAgent:
    def next_step(self, observations):
        if not observations:
            return ToolStep("topology", {})
        return FinalStep("restore_dns", "incorrect diagnosis", "I propose DNS anyway",
                         ("topology",), 0.99)


def test_independent_gate_blocks_wrong_but_cited_action_before_sandbox(lab):
    instance, runner = lab
    instance.inject("proxy-misroute")
    proposed = instance.investigate(agent=WrongButCitedAgent())
    incident = proposed["active_incident"]
    assert incident["raw_action"] == "restore_dns"  # model answer preserved
    assert incident["action"] == "none"  # never promoted without evidence
    assert incident["evidence_gate"]["allowed"] is False
    with pytest.raises(LabConflict, match="unsafe or unknown"):
        instance.verify()
    assert not any(name.startswith("proofops-v-") for name in runner.projects)
    assert instance._state()["active_incident"]["verification"] is None
    instance.reset()


class NoStandbyFakeRunner(FakeDockerRunner):
    deny_standby = False

    def run(self, argv, env, cwd, timeout):
        args = argv[argv.index("-p") + 2:]
        if (self.deny_standby and args[:4] == ["exec", "-T", "probe", "wget"]
            and args[-1] == f"http://{env['PROOFOPS_BACKEND_B_IP']}:8080/health"):
            self.calls.append((argv[argv.index("-p") + 1], args))
            return CommandResult(4, "", "standby unreachable")
        return super().run(argv, env, cwd, timeout)


def test_no_standby_is_a_safe_abstention(tmp_path):
    runner = NoStandbyFakeRunner()
    instance = DockerLab(root=tmp_path / "lab", runner=runner, slot=120)
    instance.start()
    try:
        stack = instance._stack(instance._state())
        stack.set_backend_a(False)
        runner.deny_standby = True
        report = investigate_readonly(RealReadOnlyTools(stack), ReferenceInvestigator(),
                                      label="rule-baseline")
        assert report["proposal"]["action"] == "none"
        assert report["proposal"]["confidence"] == 0.0
    finally:
        runner.deny_standby = False
        instance.stop()
