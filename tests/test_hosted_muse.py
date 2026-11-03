"""Offline, fake-HTTP coverage for hosted Muse on an isolated fake Docker stack.

NO hosted API requests, real Docker mutation, or paid inference in these tests.
"""
from __future__ import annotations

import json
import urllib.request

import pytest

from proofops.hosted_muse import HostedMuseProvider, HOSTED_MUSE_CONSENT_PHRASE
from proofops.investigation import FinalStep, ToolStep
from proofops.model_protocol import (
    InvalidModelStep, WireInvestigator, build_request, parse_step,
)
from proofops.real_lab import DockerLab, LabConflict, main
from test_real_lab import FakeDockerRunner


class FakeHTTPResponse:
    def __init__(self, content: dict):
        self.data = json.dumps(content).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, amount: int):
        assert amount >= len(self.data)
        return self.data


def fake_chat(choice_or_details, model="muse-spark-1.3", *, finish="stop"):
    return FakeHTTPResponse({
        "model": model,
        "choices": [{"finish_reason": finish,
                     "message": {"content": json.dumps(choice_or_details)}}],
        "usage": {"prompt_tokens": 40, "completion_tokens": 20},
    })


def patch_fake_network(monkeypatch, replies, calls, *, model="muse-spark-1.3"):
    class Opener:
        def open(self, req, timeout):
            body = json.loads(req.data)
            calls.append((req, body, timeout))
            if not replies:
                pytest.fail("Unexpected additional hosted model request")
            return fake_chat(replies.pop(0), model=model)

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())


def complete_observations():
    return (
        {"evidence_id": "topology", "declared_backends": {
            "backend-a": "10.223.120.21", "backend-b": "10.223.120.22"},
            "expected_gateway_ip": "10.223.120.10"},
        {"evidence_id": "customer-path", "healthy": False},
        {"evidence_id": "dns", "expected_ip": "10.223.120.10",
         "resolved_ip": "10.223.120.99", "matches_expected": False},
        {"evidence_id": "gateway", "upstream_ip": "10.223.120.21",
         "declared_ips": ["10.223.120.21", "10.223.120.22"], "allowed": True},
        {"evidence_id": "backend-a", "healthy": True},
        {"evidence_id": "backend-b", "healthy": True},
    )


def test_provider_selection_is_fixed_and_no_key_fallback(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    monkeypatch.setenv("META_BASE_URL", "https://untrusted.example")
    with pytest.raises(ValueError, match="MODEL_API_KEY"):
        HostedMuseProvider("official-meta")
    with pytest.raises(ValueError, match="BASETEN_API_KEY"):
        HostedMuseProvider("baseten")
    with pytest.raises(ValueError, match="official-meta or baseten"):
        HostedMuseProvider("arbitrary", api_key="dummy")
    meta = HostedMuseProvider("official-meta", api_key="dummy")
    base = HostedMuseProvider("baseten", api_key="dummy")
    assert meta.endpoint == "https://api.meta.ai/v1/chat/completions"
    assert base.endpoint == "https://inference.baseten.co/v1/chat/completions"


def test_cli_requires_explicit_provider_consent_and_key(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_API_KEY", "dummy-test-only")
    monkeypatch.setenv("BASETEN_API_KEY", "dummy-test-only")
    args = ["investigate", "--investigator", "hosted-muse",
            "--root", str(tmp_path / "missing-state")]
    with pytest.raises(SystemExit) as missing_provider:
        main(args)
    assert missing_provider.value.code == 2
    with pytest.raises(SystemExit) as missing_consent:
        main(args + ["--muse-provider", "official-meta"])
    assert missing_consent.value.code == 2
    # Authorization allows reaching the controller, but without a started lab
    # it must fail there, with no model or Docker recovery performed.
    assert main(args + ["--muse-provider", "official-meta",
                        "--confirm-cloud", HOSTED_MUSE_CONSENT_PHRASE]) == 2


def test_missing_topology_cannot_offer_proxy_repair(monkeypatch):
    observations = tuple(o for o in complete_observations() if o["evidence_id"] != "topology")
    calls = []
    patch_fake_network(monkeypatch, [{"choice": "topology"}], calls)
    provider = HostedMuseProvider("official-meta", api_key="dummy")
    step = parse_step(provider.generate_step(build_request(observations)))
    assert step == ToolStep("topology", {})
    options = calls[0][1]["response_format"]["json_schema"]["schema"]["properties"]["choice"]["enum"]
    assert "final_restore_proxy" not in options
    assert "final_restore_dns" not in options
    assert "final_failover" not in options
    assert "final_none" in options
    assert "topology" in options


def test_full_observations_enable_proposals_but_never_autofill_citations(monkeypatch):
    calls = []
    patch_fake_network(monkeypatch,
                       [{"choice": "final_restore_dns"},
                        {"root_cause": "DNS target differs", "explanation": "Propose DNS restoration",
                         "confidence": 0.9, "evidence_ids": ["dns"]}], calls)
    provider = HostedMuseProvider("official-meta", api_key="dummy")
    step = parse_step(provider.generate_step(build_request(complete_observations())))
    assert step == FinalStep("restore_dns", "DNS target differs", "Propose DNS restoration",
                             ("dns",), 0.9)
    assert provider.calls == 2
    assert provider.prompt_tokens == 80
    assert calls[1][1]["messages"][1]["content"].find("required_evidence_ids") >= 0
    assert "authorization" not in json.dumps(calls[0][1]).lower()
    assert calls[0][1]["response_format"]["json_schema"]["strict"] is True


def test_baseten_transport_uses_distinct_endpoint_and_json_mode(monkeypatch):
    calls = []
    patch_fake_network(monkeypatch, [{"choice": "final_none"},
                                     {"root_cause": "Unknown", "explanation": "Abstaining",
                                      "confidence": 0.1, "evidence_ids": []}],
                       calls, model="meta/Muse-Spark-open-816B-42B")
    provider = HostedMuseProvider("baseten", api_key="dummy")
    result = parse_step(provider.generate_step(build_request(())))
    assert result.action == "none"
    assert len(calls) == 2
    assert all(req.full_url == "https://inference.baseten.co/v1/chat/completions"
               for req, _, _ in calls)
    assert calls[0][1]["response_format"] == {"type": "json_object"}
    assert calls[0][1]["max_tokens"] == 2048


def test_model_mismatch_and_truncated_reply_fail_closed(monkeypatch):
    calls = []
    patch_fake_network(monkeypatch, [{"choice": "final_none"}], calls,
                       model="unknown-model")
    with pytest.raises(InvalidModelStep, match="differed"):
        HostedMuseProvider("official-meta", api_key="dummy").generate_step(build_request(()))

    class Opener:
        def open(self, req, timeout):
            return fake_chat({"choice": "topology"}, finish="length")
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    with pytest.raises(InvalidModelStep, match="incomplete"):
        HostedMuseProvider("official-meta", api_key="dummy").generate_step(build_request(()))


def test_wrong_action_is_kept_and_independent_gate_rejects_it(monkeypatch, tmp_path):
    calls = []
    replies = [{"choice": c} for c in (
        "topology", "customer_path", "lookup_dns", "inspect_gateway",
        "probe_backend_a", "final_restore_proxy")]
    replies.append({"root_cause": "Wrong diagnosis", "explanation": "Incorrect proxy action",
                    "confidence": 0.83,
                    "evidence_ids": ["topology", "customer-path", "dns", "gateway", "backend-a"]})
    patch_fake_network(monkeypatch, replies, calls)
    lab = DockerLab(root=tmp_path / "lab", slot=120, runner=FakeDockerRunner())
    try:
        lab.start()
        lab.inject("dns-drift")
        provider = HostedMuseProvider("official-meta", api_key="dummy")
        state = lab.investigate(agent=WireInvestigator(provider), label=provider.source_label)
        incident = state["active_incident"]
        assert incident["raw_action"] == "restore_proxy"
        assert incident["action"] == "none"
        assert incident["evidence_gate"]["allowed"] is False
        assert incident["verification"] is None
        with pytest.raises(LabConflict):
            lab.verify()
    finally:
        lab.stop()


def test_valid_model_dns_proposal_passes_gate_but_still_needs_approval(monkeypatch, tmp_path):
    calls = []
    replies = [{"choice": c} for c in (
        "topology", "customer_path", "lookup_dns", "inspect_gateway",
        "probe_backend_a", "final_restore_dns")]
    replies.append({"root_cause": "DNS points away from gateway",
                    "explanation": "Customer fails while gateway and selected backend remain healthy",
                    "confidence": 0.87,
                    "evidence_ids": ["topology", "customer-path", "dns", "gateway", "backend-a"]})
    patch_fake_network(monkeypatch, replies, calls)
    lab = DockerLab(root=tmp_path / "lab", slot=120, runner=FakeDockerRunner())
    try:
        lab.start()
        lab.inject("dns-drift")
        provider = HostedMuseProvider("official-meta", api_key="dummy")
        state = lab.investigate(agent=WireInvestigator(provider), label=provider.source_label)
        inc = state["active_incident"]
        assert inc["raw_action"] == inc["action"] == "restore_dns"
        assert inc["evidence_gate"]["allowed"] is True
        assert inc["proof"] is None
        assert provider.calls == 7
        # Once a hosted AI proposal qualifies, local rule diagnosis must not
        # overwrite its provenance without explicit reset/repair lifecycle.
        with pytest.raises(LabConflict, match="Qualified hosted-AI"):
            lab.analyze()
        verified = lab.verify()
        assert verified["active_incident"]["verification"]["success"] is True
        assert verified["service_status"] == "critical"
        assert verified["active_incident"]["proof"] is None
        # No automatic active repair. The separate approval API remains unchanged.
    finally:
        lab.stop()


def test_official_meta_reasoning_effort_is_explicit_and_phase_bounded(monkeypatch):
    # No model is contacted: intercept the exact official API request payload.
    calls = []
    patch_fake_network(monkeypatch, [
        {"choice": "final_restore_dns"},
        {"root_cause": "Observed DNS drift", "explanation": "DNS record mismatch",
         "confidence": 0.76,
         "evidence_ids": ["topology", "customer-path", "dns", "gateway", "backend-a"]},
    ], calls)
    provider = HostedMuseProvider("official-meta", api_key="dummy", request_budget=2)
    result = parse_step(provider.generate_step(build_request(complete_observations())))
    assert result.action == "restore_dns"
    assert provider.calls == 2
    first, second = (call[1] for call in calls)
    assert first["reasoning_effort"] == "minimal"
    assert first["max_completion_tokens"] == 1024
    assert second["reasoning_effort"] == "low"
    assert second["max_completion_tokens"] == 2048
    for _, body, _ in calls:
        assert body["model"] == "muse-spark-1.3"
        assert body["store"] is False
        assert body["response_format"]["json_schema"]["strict"] is True
        assert "BASETEN_API_KEY" not in json.dumps(body)


def test_official_meta_truncation_is_reported_without_hidden_retries(monkeypatch):
    # Truncated reasoning is counted, rejected, and NEVER retried silently.
    calls = []

    class Opener:
        def open(self, req, timeout):
            calls.append(json.loads(req.data))
            return FakeHTTPResponse({
                "model": "muse-spark-1.3",
                "choices": [{"finish_reason": "length", "message": {"content": None}}],
                "usage": {"prompt_tokens": 349, "completion_tokens": 1024,
                          "completion_tokens_details": {"reasoning_tokens": 1000}},
            })

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    provider = HostedMuseProvider("official-meta", api_key="fake-secret-do-not-log", request_budget=1)
    with pytest.raises(InvalidModelStep, match="incomplete or truncated") as failure:
        provider.generate_step(build_request(()))
    assert provider.calls == len(calls) == 1
    assert provider.prompt_tokens == 349
    assert provider.completion_tokens == 1024
    assert provider.reasoning_tokens == 1000
    assert "fake-secret" not in str(failure.value)
    assert calls[0]["reasoning_effort"] == "minimal"
    assert calls[0]["max_completion_tokens"] == 1024
