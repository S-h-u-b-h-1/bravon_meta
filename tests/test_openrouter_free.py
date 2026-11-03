"""Free hosted-model adapter is tested with mocked network; no live calls."""
import json
import urllib.error
import urllib.request

import pytest

from proofops.blind_eval import SyntheticReadOnlyTools, _make_case
from proofops.evidence_gate import assess_proposal
from proofops.investigation import FinalStep, ReferenceInvestigator, ToolStep, investigate_readonly
from proofops.model_protocol import (InvalidModelStep, ScriptedStepProvider,
                                     WireInvestigator, build_request, parse_step, to_wire)
from proofops.openrouter_free import FreeModelProvider, main, run_synthetic_case


def _full_evidence(family):
    case = _make_case(family, "test-hidden-label", 120)
    tools = SyntheticReadOnlyTools(case)
    report = investigate_readonly(tools, ReferenceInvestigator(), label="reference NOT AI")
    return case, tools, report


@pytest.mark.parametrize("family", ["dns-drift", "proxy-misroute", "backend-outage", "healthy",
                                  "compound-dns-proxy", "compound-dns-backend", "primary-no-standby",
                                  "unexplained-path"])
def test_gate_accepts_correct_reference_decisions_without_hidden_label(family):
    case, tools, report = _full_evidence(family)
    result = assess_proposal(report["proposal"], tools.observations)
    assert result.allowed, (family, result.reason)
    assert report["proposal"]["action"] == case.expected_action


@pytest.mark.parametrize("family", ["unknown-dns", "unknown-gateway"])
def test_gate_blocks_unjustified_rule_reference_action_on_missing_telemetry(family):
    # A reference baseline can itself be overconfident. The gate must remain
    # independent of that baseline and reject a claim unsupported by telemetry.
    case, tools, report = _full_evidence(family)
    assert report["proposal"]["action"] != "none"
    assert not assess_proposal(report["proposal"], tools.observations).allowed


def test_gate_rejects_wrong_repair_with_genuine_citations():
    _, tools, report = _full_evidence("dns-drift")
    proposal = {**report["proposal"], "action": "restore_proxy"}
    verdict = assess_proposal(proposal, tools.observations)
    assert not verdict.allowed
    assert "DNS" in verdict.reason
    assert proposal["action"] == "restore_proxy"  # no silent correction


def test_gate_rejects_compound_fault_even_if_model_is_confident():
    _, tools, report = _full_evidence("compound-dns-proxy")
    fake = {**report["proposal"], "action": "restore_proxy", "confidence": 1.0}
    assert not assess_proposal(fake, tools.observations).allowed
    fake["action"] = "restore_dns"
    assert not assess_proposal(fake, tools.observations).allowed


def test_gate_rejects_missing_evidence_or_hallucinated_citations():
    _, tools, report = _full_evidence("dns-drift")
    proposal = report["proposal"]
    assert not assess_proposal({**proposal, "evidence_ids": ["dns"]}, tools.observations).allowed
    assert not assess_proposal({**proposal, "evidence_ids": ["imaginary"]}, tools.observations).allowed
    assert not assess_proposal(proposal, tools.observations[:3]).allowed


def test_gate_rejects_no_backend_probe_even_with_correct_dns_and_gateway():
    _, tools, report = _full_evidence("dns-drift")
    observed = tuple(o for o in tools.observations if o["evidence_id"] not in {"backend-a", "backend-b"})
    verdict = assess_proposal({**report["proposal"], "evidence_ids": [o["evidence_id"] for o in observed]}, observed)
    assert not verdict.allowed
    assert "health" in verdict.reason.lower()


def _fake_completion(content, *, model=FreeModelProvider.MODEL, finish="stop", usage=None):
    return {"model": model, "choices": [{"finish_reason": finish, "message": {"content": content}}],
            "usage": usage or {"prompt_tokens": 114, "completion_tokens": 500,
                               "completion_tokens_details": {"reasoning_tokens": 416}}}


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, n):
        assert n == 200_001
        return json.dumps(self.payload).encode()


class CapturedOpener:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.requests = []
    def open(self, req, timeout):
        self.requests.append((req, timeout))
        obj = self.payloads.pop(0)
        if isinstance(obj, Exception):
            raise obj
        return FakeResponse(obj)


def test_provider_pins_free_model_and_never_calls_network_in_constructor(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    provider = FreeModelProvider()
    assert provider.calls == 0
    assert provider.model.endswith(":free")
    with pytest.raises(ValueError, match="pinned"):
        FreeModelProvider(model="nvidia/nemotron-3.5-lightning")
    with pytest.raises(ValueError, match="pinned"):
        FreeModelProvider(model="openrouter/free")
    monkeypatch.delenv("OPENROUTER_API_KEY")
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        FreeModelProvider()


def test_provider_sends_synthetic_only_and_one_choice_step(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    fake = CapturedOpener([_fake_completion('{"choice":"lookup_dns"}')])
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    provider = FreeModelProvider()
    step = parse_step(provider.generate_step(build_request(())))
    assert step == ToolStep("lookup_dns", {})
    assert provider.calls == 1
    req, timeout = fake.requests[0]
    assert timeout == 90.0
    assert req.full_url == "https://openrouter.ai/api/v1/chat/completions"
    assert req.get_header("Authorization") == "Bearer private-test-key"
    data = json.loads(req.data)
    assert data["model"] == FreeModelProvider.MODEL
    assert data["max_tokens"] == 4096
    assert data["reasoning"] == {"enabled": False}
    assert "response_format" not in data  # free endpoint does not support JSON schema enforcement
    assert provider.reasoning_disabled_requested is True  # requested, not confirmed upstream
    assert "private-test-key" not in json.dumps(data)
    assert "expected_action" not in json.dumps(data)
    assert "family" not in json.dumps(data)
    # Inspect offered options, not the system instructions describing the rule.
    offered = {item["name"] for item in json.loads(data["messages"][1]["content"])["choices"]}
    assert "final_none" not in offered
    assert "customer_path" in offered
    assert provider.reasoning_tokens == 416
    assert provider.compact_choice_recoveries == 0
    assert provider.invalid_reply_previews == []


@pytest.mark.parametrize("reply", ["topology", '"topology"', "  topology  "])
def test_exact_allowlisted_compact_probe_choice_preserves_model_selection(monkeypatch, reply):
    """Recover only the serialization of the real choice, without guessing."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    fake = CapturedOpener([_fake_completion(reply, usage={
        "prompt_tokens": 100, "completion_tokens": 3,
        "completion_tokens_details": {"reasoning_tokens": 0},
    })])
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    provider = FreeModelProvider()
    step = parse_step(provider.generate_step(build_request(())))
    assert step == ToolStep("topology", {})
    assert provider.calls == 1  # no additional free-tier requests
    assert provider.selections == ["topology"]
    assert provider.compact_choice_recoveries == 1
    assert provider.invalid_reply_previews == []


@pytest.mark.parametrize("reply", [
    "topology and lookup_dns", "please run topology", "final_restore_dns",
    '"unknown_option"', "```json\n{\"choice\":\"topology\"}\n```",
    "<script>alert(1)</script>",
])
def test_ambiguous_or_unlisted_text_choice_is_not_recovered(monkeypatch, reply):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    fake = CapturedOpener([_fake_completion(reply)])
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    provider = FreeModelProvider()
    with pytest.raises(InvalidModelStep):
        provider.generate_step(build_request(()))
    assert provider.calls == 1
    assert provider.compact_choice_recoveries == 0
    assert provider.selections == []


def test_three_token_failure_debug_preview_is_redacted_and_bounded(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    fake = CapturedOpener([_fake_completion("<b>private-test-key ???</b>")])
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    provider = FreeModelProvider()
    with pytest.raises(InvalidModelStep, match="one valid JSON object"):
        provider.generate_step(build_request(()))
    assert provider.calls == 1
    samples = provider.invalid_reply_previews
    assert len(samples) == 1
    assert samples[0]["phase"] == "tool selection"
    assert "private-test-key" not in json.dumps(samples)
    assert "[REDACTED_KEY]" in samples[0]["excerpt"]


def test_final_explanation_never_uses_compact_choice_fallback(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    fake = CapturedOpener([_fake_completion('{"choice":"final_none"}'),
                           _fake_completion("topology")])
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    provider = FreeModelProvider()
    with pytest.raises(InvalidModelStep, match="one valid JSON object"):
        provider.generate_step(build_request(_observations("customer_path")))
    assert provider.calls == 2
    assert provider.compact_choice_recoveries == 0
    assert provider.invalid_reply_previews[0]["phase"] == "final explanation"


def test_provider_requires_second_valid_final_and_keeps_original_decision(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    fake = CapturedOpener([
        _fake_completion('{"choice":"final_restore_dns"}'),
        _fake_completion(json.dumps({"root_cause": "DNS drift", "explanation": "Customer path failed",
                                     "confidence": 0.89,
                                     "evidence_ids": ["topology", "customer-path", "dns", "gateway", "backend-a"]})),
    ])
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    provider = FreeModelProvider()
    case, tools, _ = _full_evidence("dns-drift")
    step = parse_step(provider.generate_step(build_request(tools.observations)))
    assert step == FinalStep("restore_dns", "DNS drift", "Customer path failed",
                             ("topology", "customer-path", "dns", "gateway", "backend-a"), 0.89)
    assert provider.calls == 2
    assert provider.prompt_tokens == 228
    assert "case_id" not in json.dumps(json.loads(fake.requests[0][0].data))
    assert "expected_action" not in json.dumps(json.loads(fake.requests[1][0].data))


@pytest.mark.parametrize("response", [
    _fake_completion(None),
    _fake_completion("not json"),
    _fake_completion('{"choice":"lookup_dns"}', finish="length"),
    _fake_completion('{"choice":"lookup_dns"}', model="paid/another-model"),
    _fake_completion('{"choice":"no_such_tool"}'),
])
def test_bad_model_response_fails_closed(monkeypatch, response):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    fake = CapturedOpener([response])
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    with pytest.raises(InvalidModelStep):
        FreeModelProvider().generate_step(build_request(()))


def test_rate_limit_error_is_sanitized(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    fake = CapturedOpener([urllib.error.HTTPError(FreeModelProvider.ENDPOINT, 429,
        "secret-from-api", {}, None)])
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    with pytest.raises(InvalidModelStep) as info:
        FreeModelProvider().generate_step(build_request(()))
    assert "429" in str(info.value)
    assert "secret-from-api" not in str(info.value)
    assert "private-test-key" not in str(info.value)


def test_case_reporting_preserves_bad_model_action_and_gate_denial():
    case = _make_case("dns-drift", "x", 120)
    steps = [to_wire(x) for x in ReferenceInvestigator.PLAN]
    ids = ["topology", "customer-path", "dns", "gateway", "backend-a", "backend-b"]
    steps.append(to_wire(FinalStep("restore_proxy", "wrong idea", "bad fix", tuple(ids), 0.99)))
    report = run_synthetic_case(family="dns-drift", provider=ScriptedStepProvider(steps))
    assert report["raw_model_action"] == "restore_proxy"
    assert not report["correct"]
    assert report["unsafe_proposal"]
    assert not report["evidence_gate"]["allowed"]
    assert report["approved_for_execution"] is False
    assert report["repair_executed"] is False
    assert report["only_synthetic_evidence_transmitted"] is None


def test_successful_synthetic_case_gate_and_no_repair():
    ids = ["topology", "customer-path", "dns", "gateway", "backend-a", "backend-b"]
    steps = [to_wire(x) for x in ReferenceInvestigator.PLAN]
    steps.append(to_wire(FinalStep("restore_dns", "DNS mismatch", "backend ready", tuple(ids), 0.8)))
    report = run_synthetic_case(family="dns-drift", provider=ScriptedStepProvider(steps))
    assert report["correct"]
    assert report["evidence_gate"]["allowed"]
    assert report["model_calls"] == 7
    assert not report["repair_executed"]


def test_cli_no_key_does_not_log_secrets(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["--output", str(tmp_path / "r.json")])
    assert exc.value.code == 2
    assert not (tmp_path / "r.json").exists()
    assert "OPENROUTER_API_KEY" in capsys.readouterr().err


def test_provider_accounts_for_reasoning_usage_when_truncated(monkeypatch):
    """A bad response must not be logged as a successful zero-token reply."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-secret")
    truncated = _fake_completion(
        None, finish="length", usage={
            "prompt_tokens": 77, "completion_tokens": 4096,
            "completion_tokens_details": {"reasoning_tokens": 4080},
        })
    fake = CapturedOpener([truncated])
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    provider = FreeModelProvider()
    with pytest.raises(InvalidModelStep, match="generation cap during tool selection"):
        provider.generate_step(build_request(()))
    assert provider.calls == 1
    assert provider.request_phases == ["tool selection"]
    assert provider.finish_reasons == ["length"]
    assert provider.token_limit_events == 1
    assert provider.prompt_tokens == 77
    assert provider.completion_tokens == 4096
    assert provider.reasoning_tokens == 4080
    body = json.loads(fake.requests[0][0].data)
    assert body["reasoning"] == {"enabled": False}
    assert body["max_tokens"] == 4096


def test_provider_final_stage_also_requests_compact_no_reasoning(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-secret")
    fake = CapturedOpener([
        _fake_completion('{"choice":"final_restore_dns"}'),
        _fake_completion(json.dumps({
            "root_cause": "DNS drift", "explanation": "Known gateway differs from DNS",
            "confidence": 0.89,
            "evidence_ids": ["topology", "customer-path", "dns", "gateway", "backend-a"]}))
    ])
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    _, tools, _ = _full_evidence("dns-drift")
    provider = FreeModelProvider()
    provider.generate_step(build_request(tools.observations))
    assert provider.request_phases == ["tool selection", "final explanation"]
    assert all(json.loads(req.data)["reasoning"] == {"enabled": False}
               for req, _timeout in fake.requests)
    assert all(json.loads(req.data)["max_tokens"] == 4096
               for req, _timeout in fake.requests)


def _observations(*probes, family="dns-drift"):
    case = _make_case(family, "probe-coverage-test", 120)
    tools = SyntheticReadOnlyTools(case)
    for name in probes:
        if name.startswith("backend-"):
            tools.call("probe_backend", {"backend": name})
        else:
            tools.call(name, {})
    return tuple(tools.observations)


def test_incomplete_evidence_cannot_offer_restore_dns(monkeypatch):
    """Regression: the model finalized after three probes and the gate blocked it."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    observations = _observations("topology", "lookup_dns", "customer_path")
    fake = CapturedOpener([_fake_completion('{"choice":"final_restore_dns"}')])
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    with pytest.raises(InvalidModelStep, match="listed action"):
        FreeModelProvider().generate_step(build_request(observations))
    payload = json.loads(fake.requests[0][0].data)
    choices = {x["name"] for x in json.loads(payload["messages"][1]["content"])["choices"]}
    assert "final_restore_dns" not in choices
    assert "inspect_gateway" in choices
    assert "final_none" in choices  # safe abstention always available
    assert "expected_action" not in json.dumps(payload)


def test_missing_customer_path_cannot_prematurely_abstain(monkeypatch):
    """Reproduce the real-Docker missed repair without leaking its fault label.

    The model observed topology, DNS, both backends and gateway, but skipped
    customer_path and chose final_none. No fault-dependent shortcut should be
    supplied; only the missing customer-path observation is now offered.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    observations = _observations("topology", "lookup_dns", "inspect_gateway",
                                 "backend-a", "backend-b")
    fake = CapturedOpener([_fake_completion('{"choice":"final_none"}')])
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    provider = FreeModelProvider()
    with pytest.raises(InvalidModelStep, match="listed action"):
        provider.generate_step(build_request(observations))
    sent = json.loads(fake.requests[0][0].data)
    payload = json.loads(sent["messages"][1]["content"])
    options = {choice["name"] for choice in payload["choices"]}
    assert options == {"customer_path"}
    assert provider.selections == []  # never relabel abstention as an actual tool choice
    assert provider.calls == 1
    assert "expected_action" not in json.dumps(sent)
    assert "dns-drift" not in json.dumps(sent)


def test_abstention_allowed_after_customer_path_even_when_unresolved(monkeypatch):
    """The rule gathers symptom evidence but never forces a repair."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    observations = _observations("topology", "customer_path", "lookup_dns")
    fake = CapturedOpener([
        _fake_completion('{"choice":"final_none"}'),
        _fake_completion(json.dumps({
            "root_cause": "Uncertain cause", "explanation": "No safe change proposed",
            "confidence": 0.2, "evidence_ids": ["customer-path", "dns"]}))
    ])
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    provider = FreeModelProvider()
    result = parse_step(provider.generate_step(build_request(observations)))
    assert isinstance(result, FinalStep) and result.action == "none"
    assert provider.selections == ["final_none"]
    assert provider.calls == 2


def test_customer_path_probe_is_still_model_selected(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    observations = _observations("topology", "lookup_dns", "inspect_gateway",
                                 "backend-a", "backend-b")
    fake = CapturedOpener([_fake_completion('{"choice":"customer_path"}')])
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    provider = FreeModelProvider()
    result = parse_step(provider.generate_step(build_request(observations)))
    assert result == ToolStep("customer_path", {})
    assert provider.selections == ["customer_path"]
    assert provider.calls == 1


def test_valid_dns_coverage_offers_model_chosen_restore_dns(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    observations = _observations("topology", "lookup_dns", "customer_path", "inspect_gateway", "backend-a")
    citations = [o["evidence_id"] for o in observations]
    fake = CapturedOpener([
        _fake_completion('{"choice":"final_restore_dns"}'),
        _fake_completion(json.dumps({"root_cause": "DNS mismatch",
                                     "explanation": "Gateway and selected backend healthy",
                                     "evidence_ids": citations, "confidence": 0.88})),
    ])
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    provider = FreeModelProvider()
    result = parse_step(provider.generate_step(build_request(observations)))
    assert isinstance(result, FinalStep)
    assert result.action == "restore_dns"
    assert provider.calls == 2
    assert assess_proposal({"action": result.action, "evidence_ids": list(result.evidence_ids)}, observations).allowed
    sent = json.loads(fake.requests[0][0].data)
    choices = {x["name"] for x in json.loads(sent["messages"][1]["content"])["choices"]}
    assert "final_restore_dns" in choices
    assert "final_failover" not in choices  # needs healthy independent standby probe


def test_both_backend_probes_required_if_selected_upstream_cannot_be_identified():
    from proofops.evidence_gate import prerequisite_evidence_ids
    data = [
        {"evidence_id": "topology", "declared_backends": {"backend-a": "10.1.1.2", "backend-b": "10.1.1.3"}},
        {"evidence_id": "customer-path", "healthy": False},
        {"evidence_id": "dns", "matches_expected": False},
        {"evidence_id": "gateway", "upstream_ip": "unknown-target"},
    ]
    assert prerequisite_evidence_ids("restore_dns", data) == (
        "topology", "customer-path", "dns", "gateway", "backend-a", "backend-b"
    )
    data[-1]["upstream_ip"] = "10.1.1.3"
    assert prerequisite_evidence_ids("restore_dns", data)[-1] == "backend-b"


def test_simulated_free_model_must_probe_before_qualified_repair(monkeypatch):
    """End-to-end fake API interaction, never live traffic or Docker execution."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    picks = ["topology", "lookup_dns", "customer_path", "inspect_gateway",
             "probe_backend_a", "final_restore_dns"]
    citations = ["topology", "dns", "customer-path", "gateway", "backend-a"]
    response_stream = [_fake_completion(json.dumps({"choice": pick})) for pick in picks]
    response_stream.append(_fake_completion(json.dumps({
        "root_cause": "DNS points to wrong IP",
        "explanation": "The selected backend and proxy are healthy",
        "evidence_ids": citations, "confidence": 0.8,
    })))
    fake = CapturedOpener(response_stream)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    provider = FreeModelProvider()
    report = run_synthetic_case(family="dns-drift", provider=provider)
    assert report["correct"] is True
    assert report["evidence_gate"]["allowed"] is True
    assert report["model_calls"] == 7
    assert report["tool_calls"] == 5
    assert report["repair_executed"] is False
    assert len(fake.requests) == 7
    for step, (req, _) in enumerate(fake.requests[:5]):
        user_payload = json.loads(json.loads(req.data)["messages"][1]["content"])
        choices = {opt["name"] for opt in user_payload["choices"]}
        assert "final_restore_dns" not in choices, step
    final_request = json.loads(json.loads(fake.requests[5][0].data)["messages"][1]["content"])
    assert "final_restore_dns" in {opt["name"] for opt in final_request["choices"]}
    assert all("expected_action" not in json.dumps(req.data.decode()) for req, _ in fake.requests)


def test_compact_first_reply_still_requires_five_probes_and_gate_qualification(monkeypatch):
    """Regression for an occasional plain `topology` response at the first call."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    picks = ["topology", "lookup_dns", "customer_path", "inspect_gateway",
             "probe_backend_a", "final_restore_dns"]
    evidence = ["topology", "dns", "customer-path", "gateway", "backend-a"]
    responses = [_fake_completion("topology")]
    responses += [_fake_completion(json.dumps({"choice": choice})) for choice in picks[1:]]
    responses.append(_fake_completion(json.dumps({
        "root_cause": "DNS mismatch", "explanation": "Backend and proxy healthy",
        "evidence_ids": evidence, "confidence": 0.85,
    })))
    fake = CapturedOpener(responses)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    provider = FreeModelProvider()
    report = run_synthetic_case(family="dns-drift", provider=provider)
    assert report["raw_model_action"] == "restore_dns"
    assert report["correct"] is True
    assert report["evidence_gate"]["allowed"] is True
    assert report["model_calls"] == 7
    assert report["tool_calls"] == 5
    assert report["compact_choice_recoveries"] == 1
    assert report["invalid_reply_previews"] == []
    assert report["repair_executed"] is False
    assert len(fake.requests) == 7


def test_citation_omission_is_preserved_blocked_and_diagnosed(monkeypatch):
    """A right action with missing citations is not silently made gate-qualified."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    picks = ["topology", "lookup_dns", "customer_path", "inspect_gateway",
             "probe_backend_a", "final_restore_dns"]
    responses = [_fake_completion(json.dumps({"choice": pick})) for pick in picks]
    # Simulates real model correctly proposing DNS repair but citing only DNS.
    responses.append(_fake_completion(json.dumps({
        "root_cause": "DNS drift", "explanation": "Wrong DNS answer",
        "evidence_ids": ["dns"], "confidence": 0.8,
    })))
    fake = CapturedOpener(responses)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    report = run_synthetic_case(family="dns-drift", provider=FreeModelProvider())
    assert report["raw_model_action"] == "restore_dns"
    assert report["correct"] is True
    assert report["evidence_gate"]["allowed"] is False
    assert "Missing cited" in report["evidence_gate"]["reason"]
    gap = report["evidence_gap"]
    assert gap["missing_probe_ids"] == []
    assert set(gap["missing_citation_ids"]) == {
        "topology", "customer-path", "gateway", "backend-a"
    }
    assert gap["model_cited_ids"] == ["dns"]
    assert report["repair_executed"] is False
    # Only actual, previously observed IDs are used for the prompt.
    final_payload = json.loads(json.loads(fake.requests[6][0].data)["messages"][1]["content"])
    assert set(final_payload["required_evidence_ids"]) == {
        "topology", "customer-path", "dns", "gateway", "backend-a"
    }
    assert final_payload["response_shape"]["evidence_ids"] == final_payload["required_evidence_ids"]
    assert "expected_action" not in json.dumps(final_payload)
    assert "family" not in json.dumps(final_payload)


def test_successful_citations_produce_no_evidence_gap(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")
    picks = ["topology", "lookup_dns", "customer_path", "inspect_gateway",
             "probe_backend_a", "final_restore_dns"]
    responses = [_fake_completion(json.dumps({"choice": pick})) for pick in picks]
    citations = ["topology", "customer-path", "dns", "gateway", "backend-a"]
    responses.append(_fake_completion(json.dumps({
        "root_cause": "DNS drift", "explanation": "Gateway and backend are fine",
        "evidence_ids": citations, "confidence": 0.8,
    })))
    fake = CapturedOpener(responses)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: fake)
    report = run_synthetic_case(family="dns-drift", provider=FreeModelProvider())
    assert report["evidence_gate"]["allowed"] is True
    assert report["evidence_gap"]["missing_citation_ids"] == []
    assert report["evidence_gap"]["missing_probe_ids"] == []
    assert report["repair_executed"] is False
