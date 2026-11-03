"""Regression for premature Ollama completion; no models, Docker or HTTP calls."""
import json
import urllib.request

import pytest

from proofops.investigation import ToolStep
from proofops.model_protocol import (
    InvalidModelStep, OllamaLocalProvider, build_request, parse_step,
)


class _FakeResponse:
    def __init__(self, model_reply):
        self.content = json.dumps({
            "message": {"content": json.dumps(model_reply)},
            "done": True,
            "done_reason": "stop",
        }).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, limit):
        return self.content


def _capture_requests(monkeypatch, model_reply):
    sent = []

    class Opener:
        def open(self, request, timeout):
            sent.append(json.loads(request.data))
            return _FakeResponse(model_reply)

    monkeypatch.setattr(urllib.request, "build_opener", lambda *_: Opener())
    return sent


# Mirrors the five probes that the real Llama investigator used on DNS drift.
# It intentionally lacks the required topology observation.
MISSING_TOPOLOGY = (
    {"evidence_id": "dns", "matches_expected": False},
    {"evidence_id": "customer-path", "healthy": False},
    {"evidence_id": "backend-a", "healthy": True},
    {"evidence_id": "gateway", "allowed": True},
    {"evidence_id": "backend-b", "healthy": True},
)


def _offered(sent):
    return sent[0]["format"]["properties"]["choice"]["enum"]


def test_missing_topology_blocks_premature_repair_choices(monkeypatch):
    sent = _capture_requests(monkeypatch, {"choice": "topology"})
    step = parse_step(OllamaLocalProvider().generate_step(build_request(MISSING_TOPOLOGY)))
    assert step == ToolStep("topology", {})
    choices = set(_offered(sent))
    assert "topology" in choices
    assert "final_none" in choices  # preserve model abstention
    assert not choices.intersection({
        "final_restore_dns", "final_restore_proxy", "final_failover"
    })
    assert len(sent) == 1


def test_model_attempting_uncited_early_repair_fails_closed(monkeypatch):
    sent = _capture_requests(monkeypatch, {"choice": "final_restore_proxy"})
    with pytest.raises(InvalidModelStep, match="Local model choice failed schema validation"):
        OllamaLocalProvider().generate_step(build_request(MISSING_TOPOLOGY))
    assert len(sent) == 1


def test_qualified_probe_coverage_offers_repair_without_forcing_it(monkeypatch):
    observed = (
        {"evidence_id": "topology", "declared_backends": {
            "backend-a": "10.223.120.21", "backend-b": "10.223.120.22"}},
        {"evidence_id": "customer-path", "healthy": False},
        {"evidence_id": "dns", "matches_expected": False},
        {"evidence_id": "gateway", "upstream_ip": "10.223.120.21", "allowed": True},
        {"evidence_id": "backend-a", "healthy": True},
    )
    sent = _capture_requests(monkeypatch, {"choice": "probe_backend_b"})
    step = parse_step(OllamaLocalProvider().generate_step(build_request(observed)))
    assert step == ToolStep("probe_backend", {"backend": "backend-b"})
    choices = set(_offered(sent))
    assert "final_restore_dns" in choices
    assert "final_restore_proxy" in choices  # coverage, NOT semantic approval
    assert "final_none" in choices
    assert "final_failover" not in choices  # standby evidence not yet collected


def test_selected_standby_must_be_probed_before_dns_final(monkeypatch):
    observed = (
        {"evidence_id": "topology", "declared_backends": {
            "backend-a": "10.223.120.21", "backend-b": "10.223.120.22"}},
        {"evidence_id": "customer-path", "healthy": False},
        {"evidence_id": "dns", "matches_expected": False},
        {"evidence_id": "gateway", "upstream_ip": "10.223.120.22", "allowed": True},
        {"evidence_id": "backend-a", "healthy": True},
    )
    sent = _capture_requests(monkeypatch, {"choice": "probe_backend_b"})
    OllamaLocalProvider().generate_step(build_request(observed))
    assert "final_restore_dns" not in _offered(sent)
    assert "final_none" in _offered(sent)
    assert "probe_backend_b" in _offered(sent)
