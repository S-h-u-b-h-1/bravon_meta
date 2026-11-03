"""Opt-in free-model Docker bridge tests; all network and Docker calls are simulated.

These tests DO NOT make any OpenRouter requests or use a Docker daemon.
"""
from __future__ import annotations

import json

import pytest

from proofops.investigation import FinalStep, ReferenceInvestigator, ToolStep
from proofops.model_protocol import ScriptedStepProvider, WireInvestigator, to_wire
from proofops.real_lab import (
    CLOUD_CONSENT_PHRASE, CONFIRM_PHRASE, DockerLab, LabConflict, main,
)
from test_real_lab import FakeDockerRunner


@pytest.fixture
def lab(tmp_path):
    fake = FakeDockerRunner()
    instance = DockerLab(root=tmp_path / "disposable", runner=fake, slot=120)
    instance.start()
    yield instance, fake
    instance.stop()


def scripted_investigator(action):
    observations = ("topology", "customer-path", "dns", "gateway", "backend-a")
    selections = [
        ToolStep("topology", {}),
        ToolStep("customer_path", {}),
        ToolStep("lookup_dns", {}),
        ToolStep("inspect_gateway", {}),
        ToolStep("probe_backend", {"backend": "backend-a"}),
        FinalStep(action, "diagnosed", "bounded evidence-based proposal", observations, 0.9),
    ]
    return WireInvestigator(ScriptedStepProvider([to_wire(s) for s in selections]))


def test_actual_disposable_probe_path_can_promote_qualified_ai_repair(lab):
    instance, runner = lab
    instance.inject("dns-drift")
    before = len(runner.calls)
    result = instance.investigate(agent=scripted_investigator("restore_dns"),
                                  label="FAKE FREE MODEL (OFFLINE TEST)")
    incident = result["active_incident"]
    assert incident["raw_action"] == "restore_dns"
    assert incident["action"] == "restore_dns"
    assert incident["evidence_gate"]["allowed"] is True
    assert incident["investigation"]["tool_calls"] == 5
    assert incident["investigation"]["executed_repair"] is False
    assert result["service_status"] == "critical"  # investigation does not repair
    assert all(args[0] == "exec" for _, args in runner.calls[before:])
    assert not any(name.startswith("proofops-v-") for name in runner.projects)
    with pytest.raises(LabConflict, match="verification"):
        instance.repair(approved=True, expected_revision=result["revision"],
                        confirmation=CONFIRM_PHRASE)
    verified = instance.verify()
    assert verified["active_incident"]["verification"]["success"] is True
    with pytest.raises(LabConflict, match="approval"):
        instance.repair(approved=False, expected_revision=verified["revision"],
                        confirmation=CONFIRM_PHRASE)
    repaired = instance.repair(approved=True, expected_revision=verified["revision"],
                               confirmation=CONFIRM_PHRASE)
    assert repaired["service_status"] == "healthy"
    assert repaired["active_incident"]["proof"]["action"] == "restore_dns"


def test_wrong_but_fully_cited_model_decision_never_reaches_verifier(lab):
    instance, runner = lab
    instance.inject("dns-drift")
    output = instance.investigate(agent=scripted_investigator("restore_proxy"),
                                  label="FAKE FREE MODEL (OFFLINE TEST)")
    incident = output["active_incident"]
    assert incident["raw_action"] == "restore_proxy"
    assert incident["investigation"]["proposal"]["action"] == "restore_proxy"
    assert incident["action"] == "none"
    assert incident["evidence_gate"]["allowed"] is False
    assert output["service_status"] == "critical"
    before = len(runner.calls)
    with pytest.raises(LabConflict, match="unsafe or unknown"):
        instance.verify()
    assert len(runner.calls) == before
    assert not any(name.startswith("proofops-v-") for name in runner.projects)


def test_invalid_response_does_not_change_state(lab):
    instance, _ = lab
    instance.inject("dns-drift")
    class InvalidProvider:
        def generate_step(self, request):
            return "{not json"
    with pytest.raises(ValueError):
        instance.investigate(agent=WireInvestigator(InvalidProvider()), label="FAKE FREE MODEL")
    assert instance._state()["active_incident"]["status"] == "open"
    assert instance._state()["active_incident"]["action"] is None


def test_analyze_switches_provenance_back_to_rules_after_gate_rejection(lab):
    instance, _ = lab
    instance.inject("dns-drift")
    instance.investigate(agent=scripted_investigator("restore_proxy"), label="FAKE FREE MODEL")
    output = instance.analyze()
    incident = output["active_incident"]
    assert incident["action"] == "restore_dns"
    assert incident["diagnostic_source"] == "real-probe-rules (not Meta)"
    assert incident["investigation"] is None
    assert incident["evidence_gate"] is None
    assert incident["raw_action"] is None


def test_hosted_cli_fails_closed_without_explicit_consent_or_secret(tmp_path, monkeypatch):
    root = tmp_path / "not-made"
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    with pytest.raises(SystemExit) as exc:
        main(["investigate", "--investigator", "openrouter-free", "--root", str(root)])
    assert exc.value.code == 2
    assert not root.exists()

    monkeypatch.delenv("OPENROUTER_API_KEY")
    with pytest.raises(SystemExit) as exc:
        main(["investigate", "--investigator", "openrouter-free", "--root", str(root),
              "--confirm-cloud", CLOUD_CONSENT_PHRASE])
    assert exc.value.code == 2
    assert not root.exists()


def test_hosted_cli_consent_uses_only_free_adapter_and_fixed_probes(lab, monkeypatch, capsys):
    instance, _ = lab
    instance.inject("dns-drift")
    import proofops.real_lab as lab_module
    import proofops.openrouter_free as model_module
    constructed = []

    class OfflineFreeProvider:
        model = model_module.FreeModelProvider.MODEL
        def __init__(self, *, progress=None):
            constructed.append(self)
            self.baseline = ReferenceInvestigator()
            self.progress = progress
            self.calls = 0
            self.prompt_tokens = 0
            self.completion_tokens = 0
            self.reasoning_tokens = 0
            self.compact_choice_recoveries = 0
            self.requests = []
        def generate_step(self, request):
            self.requests.append(request)
            self.calls += 1
            return to_wire(self.baseline.next_step(tuple(request["observations"])))

    monkeypatch.setattr(lab_module, "DockerLab", lambda **kwargs: instance)
    monkeypatch.setattr(model_module, "FreeModelProvider", OfflineFreeProvider)
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    assert main(["investigate", "--investigator", "openrouter-free", "--confirm-cloud",
                 CLOUD_CONSENT_PHRASE]) == 0
    outer = capsys.readouterr().out
    assert "openrouter-free:" in outer
    assert "private-test-key" not in outer
    assert '"raw_action": "restore_dns"' in outer
    assert '"promoted_action": "restore_dns"' in outer
    assert constructed and constructed[0].model.endswith(":free")
    assert constructed[0].calls == 7
    assert "private-test-key" not in json.dumps(constructed[0].requests)
    assert "scenario" not in json.dumps(constructed[0].requests)
    assert "dns-drift" not in json.dumps(constructed[0].requests)
    for request in constructed[0].requests:
        assert len(request["observations"]) <= 6
        for obs in request["observations"]:
            assert set(obs).issubset({
                "evidence_id", "host", "expected_resolver_ip", "expected_gateway_ip",
                "declared_backends", "healthy", "serving_backend", "resolved_ip",
                "expected_ip", "matches_expected", "upstream_ip", "declared_ips",
                "allowed", "backend",
            })
    assert instance._state()["active_incident"]["evidence_gate"]["allowed"] is True


def test_recovery_refuses_legacy_or_tampered_model_gate(lab):
    """A persisted AI proposal without a stored gate cannot reach verification."""
    instance, runner = lab
    instance.inject("dns-drift")
    instance.investigate(agent=scripted_investigator("restore_dns"), label="FAKE FREE MODEL")
    state = instance._state()
    state["active_incident"]["evidence_gate"] = None
    instance._save(state)
    sandbox_before = [p for p in runner.projects if p.startswith("proofops-v-")]
    with pytest.raises(LabConflict, match="Independent evidence gate"):
        instance.verify()
    assert not sandbox_before
    assert not any(p.startswith("proofops-v-") for p in runner.projects)


def test_qualified_hosted_ai_cannot_be_overwritten_and_proof_binds_its_source(lab):
    instance, _ = lab
    instance.inject("dns-drift")
    result = instance.investigate(
        agent=scripted_investigator("restore_dns"),
        label="openrouter-free:nvidia/nemotron-3.5-lightning:free (OFFLINE FAKE)",
    )
    before = instance._state()["active_incident"]
    assert before["evidence_gate"]["allowed"] is True
    with pytest.raises(LabConflict, match="locked"):
        instance.analyze()
    with pytest.raises(LabConflict, match="locked"):
        instance.investigate(agent=ReferenceInvestigator())
    assert instance._state()["active_incident"] == before
    verified = instance.verify()
    with pytest.raises(LabConflict, match="already verified"):
        instance.analyze()
    recovered = instance.repair(
        approved=True, expected_revision=verified["revision"], confirmation=CONFIRM_PHRASE
    )
    incident = recovered["active_incident"]
    proof = incident["proof"]
    assert proof["diagnostic_source"].startswith("openrouter-free:")
    assert proof["raw_action"] == "restore_dns"
    assert proof["evidence_gate"]["allowed"] is True
    assert len(proof["investigation_digest"]) == 64
    assert recovered["history"][-1]["diagnostic_source"] == proof["diagnostic_source"]


def test_unqualified_hosted_decision_still_allows_manual_rule_fallback(lab):
    instance, _ = lab
    instance.inject("dns-drift")
    instance.investigate(
        agent=scripted_investigator("restore_proxy"),
        label="openrouter-free:nvidia/nemotron-3.5-lightning:free (OFFLINE FAKE)",
    )
    assert instance.analyze()["active_incident"]["action"] == "restore_dns"
