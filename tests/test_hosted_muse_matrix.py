"""Offline hosted-Muse fault matrix using fake HTTP and a fake Docker runner.

No requests to Meta/Baseten, no real Docker, no credentials, and no cloud spend.
Scripted fake model decisions are fixtures, NOT claims of model accuracy.
"""
from __future__ import annotations

import pytest

from proofops.hosted_muse import HostedMuseProvider
from proofops.model_protocol import WireInvestigator
from proofops.real_lab import CONFIRM_PHRASE, DockerLab, LabConflict
from test_hosted_muse import patch_fake_network
from test_real_lab import FakeDockerRunner


PROBE_CHOICES = (
    "topology", "customer_path", "lookup_dns", "inspect_gateway",
    "probe_backend_a", "probe_backend_b",
)
ALL_EVIDENCE_IDS = (
    "topology", "customer-path", "dns", "gateway", "backend-a", "backend-b",
)
FAULTS = (
    pytest.param("dns-drift", "restore_dns", {"dns-record", "e2e"}, id="dns"),
    pytest.param("proxy-misroute", "restore_proxy",
                 {"proxy-route", "upstream-health", "e2e"}, id="proxy"),
    pytest.param("backend-outage", "failover", {"upstream-health", "e2e"}, id="backend"),
)


def _lab(tmp_path):
    runner = FakeDockerRunner()
    return DockerLab(root=tmp_path / "runtime", runner=runner, slot=120), runner


def _model(monkeypatch, action, *, evidence_ids=ALL_EVIDENCE_IDS):
    """One deterministic fake provider trace, limited to six probes and a final."""
    calls = []
    replies = [{"choice": c} for c in PROBE_CHOICES]
    replies += [
        {"choice": "final_" + action},
        {"root_cause": "Fixture-only fault hypothesis",
         "explanation": "Fixture-only citations are independently checked",
         "confidence": 0.81,
         "evidence_ids": list(evidence_ids)},
    ]
    patch_fake_network(monkeypatch, replies, calls)
    provider = HostedMuseProvider("official-meta", api_key="fake-fixture-only")
    return provider, calls


@pytest.mark.parametrize("scenario,action,expected_failures", FAULTS)
def test_complete_fake_muse_recovery_matrix(monkeypatch, tmp_path, scenario, action, expected_failures):
    """All three fault classes: diagnosis, evidence gate, clone, approval, proof."""
    lab, runner = _lab(tmp_path)
    try:
        healthy = lab.start()
        assert healthy["service_status"] == "healthy"
        injected = lab.inject(scenario)
        assert injected["service_status"] == "critical"
        failures = {c["id"] for c in injected["checks"] if not c["passed"]}
        assert failures == expected_failures
        before_fingerprint = injected["fingerprint"]

        provider, calls = _model(monkeypatch, action)
        decided = lab.investigate(
            agent=WireInvestigator(provider), label=provider.source_label,
        )
        incident = decided["active_incident"]
        assert decided["service_status"] == "critical"
        assert decided["fingerprint"] == before_fingerprint
        assert incident["raw_action"] == action
        assert incident["action"] == action
        assert incident["evidence_gate"]["allowed"] is True
        assert incident["diagnostic_source"] == provider.source_label
        assert incident["verification"] is None
        assert incident["proof"] is None
        assert {
            step["evidence"]["evidence_id"]
            for step in incident["investigation"]["transcript"] if step["kind"] == "tool"
        } == set(ALL_EVIDENCE_IDS)
        assert provider.calls == len(PROBE_CHOICES) + 2
        assert len(calls) == provider.calls
        assert all(req.full_url == provider.endpoint for req, _, _ in calls)

        clone = lab.verify()
        clone_inc = clone["active_incident"]
        verify = clone_inc["verification"]
        assert verify["action"] == action
        assert verify["success"] is True
        assert {c["id"] for c in verify["sandbox_before"] if not c["passed"]} == failures
        assert len(verify["sandbox_after"]) == 5
        assert all(c["passed"] for c in verify["sandbox_after"])
        assert clone["service_status"] == "critical", "Clone must not repair active"
        assert clone["fingerprint"] == before_fingerprint
        assert clone_inc["proof"] is None
        assert not any(p.startswith("proofops-v-") for p in runner.projects)

        revision = clone["revision"]
        with pytest.raises(LabConflict, match="approval"):
            lab.repair(approved=False, expected_revision=revision, confirmation=CONFIRM_PHRASE)
        with pytest.raises(LabConflict, match="Stale"):
            lab.repair(approved=True, expected_revision=revision - 1, confirmation=CONFIRM_PHRASE)
        with pytest.raises(LabConflict, match="confirmation"):
            lab.repair(approved=True, expected_revision=revision, confirmation="YES")

        recovered = lab.repair(
            approved=True, expected_revision=revision, confirmation=CONFIRM_PHRASE,
        )
        proof = recovered["active_incident"]["proof"]
        assert recovered["service_status"] == "healthy"
        assert recovered["revision"] == revision + 1
        assert recovered["active_incident"]["status"] == "recovered"
        assert all(c["passed"] for c in recovered["checks"])
        assert proof["action"] == action
        assert proof["raw_action"] == action
        assert proof["diagnostic_source"] == provider.source_label
        assert proof["verification_digest"] == verify["proof_digest"]
        assert proof["result"] == "observed-recovery-in-disposable-docker-lab"
        assert len(proof["proof_digest"]) == 64
        assert len(recovered["history"]) == 1
    finally:
        lab.stop()
    assert not runner.projects


@pytest.mark.parametrize("scenario,wrong_action", [
    pytest.param("dns-drift", "restore_proxy", id="dns-to-proxy"),
    pytest.param("dns-drift", "failover", id="dns-to-failover"),
    pytest.param("proxy-misroute", "restore_dns", id="proxy-to-dns"),
    pytest.param("proxy-misroute", "failover", id="proxy-to-failover"),
    pytest.param("backend-outage", "restore_dns", id="backend-to-dns"),
    pytest.param("backend-outage", "restore_proxy", id="backend-to-proxy"),
])
def test_wrong_fake_muse_action_is_rejected_without_repair(
    monkeypatch, tmp_path, scenario, wrong_action,
):
    """Never rewrite model errors into expected repairs; preserve negative proof."""
    lab, runner = _lab(tmp_path)
    try:
        lab.start()
        broken = lab.inject(scenario)
        provider, _calls = _model(monkeypatch, wrong_action)
        result = lab.investigate(
            agent=WireInvestigator(provider), label=provider.source_label,
        )
        incident = result["active_incident"]
        assert incident["raw_action"] == wrong_action
        assert incident["investigation"]["proposal"]["action"] == wrong_action
        assert incident["evidence_gate"]["allowed"] is False
        assert incident["action"] == "none"
        assert incident["verification"] is None
        assert result["fingerprint"] == broken["fingerprint"]
        assert result["service_status"] == "critical"
        with pytest.raises(LabConflict):
            lab.verify()
        with pytest.raises(LabConflict, match="verification"):
            lab.repair(
                approved=True, expected_revision=result["revision"],
                confirmation=CONFIRM_PHRASE,
            )
        assert lab.status()["service_status"] == "critical"
        assert not any(p.startswith("proofops-v-") for p in runner.projects)
    finally:
        lab.stop()


@pytest.mark.parametrize("scenario,action,omit_id", [
    pytest.param("dns-drift", "restore_dns", "topology", id="missing-topology"),
    pytest.param("proxy-misroute", "restore_proxy", "backend-a", id="missing-primary"),
    pytest.param("backend-outage", "failover", "backend-b", id="missing-standby"),
])
def test_missing_citation_fails_closed(monkeypatch, tmp_path, scenario, action, omit_id):
    """Having an observation is not equivalent to citing it in the final answer."""
    lab, runner = _lab(tmp_path)
    try:
        lab.start()
        lab.inject(scenario)
        cited = tuple(eid for eid in ALL_EVIDENCE_IDS if eid != omit_id)
        provider, calls = _model(monkeypatch, action, evidence_ids=cited)
        result = lab.investigate(
            agent=WireInvestigator(provider), label=provider.source_label,
        )
        incident = result["active_incident"]
        assert incident["raw_action"] == action
        assert incident["investigation"]["proposal"]["evidence_ids"] == list(cited)
        assert incident["action"] == "none"
        assert incident["evidence_gate"]["allowed"] is False
        assert incident["verification"] is None
        assert result["service_status"] == "critical"
        with pytest.raises(LabConflict):
            lab.verify()
        assert len(calls) == len(PROBE_CHOICES) + 2
    finally:
        lab.stop()


@pytest.mark.parametrize("scenario", ("dns-drift", "proxy-misroute", "backend-outage"))
def test_fake_muse_abstention_is_preserved(monkeypatch, tmp_path, scenario):
    """Abstention is safe but a missed recovery, not an accuracy success."""
    lab, runner = _lab(tmp_path)
    try:
        lab.start()
        damaged = lab.inject(scenario)
        calls = []
        patch_fake_network(monkeypatch, [
            {"choice": "final_none"},
            {"root_cause": "Insufficient evidence", "explanation": "No safe action",
             "confidence": 0.14, "evidence_ids": []},
        ], calls)
        provider = HostedMuseProvider("official-meta", api_key="fake-fixture-only")
        state = lab.investigate(
            agent=WireInvestigator(provider), label=provider.source_label,
        )
        incident = state["active_incident"]
        assert incident["raw_action"] == "none"
        assert incident["action"] == "none"
        assert incident["evidence_gate"]["allowed"] is True
        assert incident["verification"] is None
        assert state["service_status"] == "critical"
        assert state["fingerprint"] == damaged["fingerprint"]
        assert provider.calls == len(calls) == 2
        with pytest.raises(LabConflict):
            lab.verify()
    finally:
        lab.stop()


def test_healthy_docker_lab_never_calls_hosted_model(monkeypatch, tmp_path):
    """No paid inference or repairs when customer service is already healthy."""
    lab, runner = _lab(tmp_path)
    try:
        lab.start()
        calls = []
        patch_fake_network(monkeypatch, [], calls)
        provider = HostedMuseProvider("official-meta", api_key="fake-fixture-only")
        with pytest.raises(LabConflict, match="No unrecovered incident"):
            lab.investigate(
                agent=WireInvestigator(provider), label=provider.source_label,
            )
        assert provider.calls == 0
        assert calls == []
        assert lab.status()["active_incident"] is None
        assert lab.status()["service_status"] == "healthy"
    finally:
        lab.stop()
