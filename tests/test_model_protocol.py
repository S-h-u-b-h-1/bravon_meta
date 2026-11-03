"""Strict wire boundary tests. All are offline; Docker calls are mocked."""
import copy
import json

import pytest

from proofops.blind_eval import SyntheticReadOnlyTools, _make_case
from proofops.investigation import FinalStep, ToolStep, investigate_readonly
from proofops.model_protocol import (
    DeterministicWireProvider, InvalidModelStep, ScriptedStepProvider,
    WireInvestigator, build_request, html_report, main, make_report, parse_step,
    to_wire, verify_report,
)
from proofops.real_lab import CONFIRM_PHRASE, DockerLab, LabConflict
from test_real_lab import FakeDockerRunner

# Generic completed read-only coverage, without an answer key or fixture label.
COMPLETE_OLLAMA_EVIDENCE = tuple({"evidence_id": key} for key in (
    "topology", "customer-path", "dns", "gateway", "backend-a", "backend-b"
))


@pytest.mark.parametrize("bad", [
    'not json', '```json\n{}\n```', '[]', '{"kind":"final","action":"restore_dns"}',
    {"kind": "tool", "name": "shell", "arguments": {"command": "rm"}},
    {"kind": "tool", "name": "lookup_dns", "arguments": {"host": "outside.test"}},
    {"kind": "tool", "name": "probe_backend", "arguments": {"backend": "localhost"}},
    {"kind": "tool", "name": "topology", "arguments": {}, "secret": "x"},
    {"kind": "final", "action": "exec", "root_cause": "x", "explanation": "x",
     "confidence": 0.5, "evidence_ids": ["dns"]},
    {"kind": "final", "action": "none", "root_cause": "x", "explanation": "x",
     "confidence": True, "evidence_ids": []},
    {"kind": "final", "action": "none", "root_cause": "x", "explanation": "x",
     "confidence": float("inf"), "evidence_ids": []},
    {"kind": "final", "action": "none", "root_cause": "x", "explanation": "x",
     "confidence": 0.0, "evidence_ids": ["dns", "dns"]},
    '{"kind":"final","action":"none","root_cause":"x", "explanation":"x", "confidence":NaN,"evidence_ids":[]}',
])
def test_invalid_provider_response_is_rejected_before_any_execution(bad):
    with pytest.raises(InvalidModelStep):
        parse_step(bad)


def test_valid_proposals_and_tool_steps_roundtrip():
    for step in [ToolStep("lookup_dns", {}), ToolStep("probe_backend", {"backend": "backend-b"}),
                 FinalStep("restore_dns", "Drift", "DNS mismatch", ("dns",), .85)]:
        assert parse_step(to_wire(step)) == step


def test_request_contains_no_hidden_labels_and_is_defensively_copied():
    case = _make_case("dns-drift", "case-1", 98)
    tools = SyntheticReadOnlyTools(case)
    obs = tools.call("topology", {})
    req = build_request(tools.observations)
    assert set(req) == {"protocol", "policy", "max_total_tool_calls", "step_number",
                        "available_tools", "observations", "allowed_final_actions", "response_format"}
    assert not any(key in json.dumps(req) for key in ("expected_action", "case-1", "case_id", "fixture_family"))
    req["observations"][0]["declared_backends"]["backend-a"] = "forged"
    assert tools.observations[0]["declared_backends"]["backend-a"] == "10.223.98.21"
    assert obs["evidence_id"] == "topology"


def test_wire_emulator_is_a_real_readonly_tool_loop_not_ai():
    case = _make_case("dns-drift", "case-1", 98)
    tools = SyntheticReadOnlyTools(case)
    agent = WireInvestigator(DeterministicWireProvider())
    report = investigate_readonly(tools, agent, label="wire (NOT AI)")
    assert report["proposal"]["action"] == "restore_dns"
    assert report["tool_calls"] == 5
    assert report["executed_repair"] is False
    assert len(agent.requests) == 6
    assert all("expected_action" not in req and "family" not in req for req in agent.requests)


def test_fabricated_evidence_reference_fails_closed():
    provider = ScriptedStepProvider([{
        "kind": "final", "action": "restore_dns", "root_cause": "DNS drift",
        "explanation": "Please do not check", "confidence": 0.99,
        "evidence_ids": ["imaginary"]}])
    tools = SyntheticReadOnlyTools(_make_case("dns-drift", "case-1", 98))
    with pytest.raises(LabConflict, match="unobserved"):
        investigate_readonly(tools, WireInvestigator(provider), label="untrusted")
    assert tools.observations == ()


def test_model_attempts_same_probe_twice_rejected():
    provider = ScriptedStepProvider([to_wire(ToolStep("topology", {})),
                                     to_wire(ToolStep("topology", {}))])
    tools = SyntheticReadOnlyTools(_make_case("dns-drift", "case-1", 98))
    with pytest.raises(InvalidModelStep, match="Repeated"):
        investigate_readonly(tools, WireInvestigator(provider), label="untrusted")
    assert len(tools.observations) == 1


def test_response_budget_and_observation_budget_reject_oversized_data():
    with pytest.raises(InvalidModelStep):
        parse_step("x" * 6500)
    with pytest.raises(InvalidModelStep):
        build_request(({"evidence_id": "topology", "log": "A" * 5000},))


def test_malicious_log_text_cannot_invoke_shell_with_deterministic_emulator():
    tools = SyntheticReadOnlyTools(_make_case("spoofed-text", "case-2", 98))
    agent = WireInvestigator(DeterministicWireProvider())
    report = investigate_readonly(tools, agent, label="wire-not-AI")
    assert report["proposal"]["action"] == "none"
    assert any("untrusted_log_excerpt" in req["observations"][-1] for req in agent.requests if req["observations"] and "untrusted_log_excerpt" in req["observations"][-1])


@pytest.mark.parametrize("scenario, action", [
    ("dns-drift", "restore_dns"), ("proxy-misroute", "restore_proxy"),
    ("backend-outage", "failover"),
])
def test_wire_emulator_plugs_into_docker_controller_but_never_executes_repair(tmp_path, scenario, action):
    runner = FakeDockerRunner()
    lab = DockerLab(root=tmp_path / "lab", runner=runner, slot=120)
    lab.start()
    try:
        lab.inject(scenario)
        before = len(runner.calls)
        investigated = lab.investigate(agent=WireInvestigator(DeterministicWireProvider()),
                                       label="wire emulator NOT AI")
        inc = investigated["active_incident"]
        assert inc["action"] == action
        assert inc["investigation"]["executed_repair"] is False
        assert inc["investigation"]["read_only"] is True
        assert all(args[0] == "exec" for _, args in runner.calls[before:])
        verified = lab.verify()
        assert verified["active_incident"]["verification"]["success"] is True
        fixed = lab.repair(approved=True, expected_revision=verified["revision"],
                           confirmation=CONFIRM_PHRASE)
        assert fixed["service_status"] == "healthy"
    finally:
        lab.stop()


def test_generated_report_replays_and_detects_tampered_content():
    report = make_report(seed=20261023, cases=42)
    assert report["summary"]["correct"] == 42
    assert report["summary"]["unsafe"] == 0
    assert report["ground_truth_not_in_request"] is True
    assert verify_report(report)[0] is True
    modified = copy.deepcopy(report)
    modified["runs"][0]["proposed_action"] = "restore_dns"
    modified["digest_sha256"] = __import__("proofops.model_protocol", fromlist=["_digest"])._digest(
        {k: v for k, v in modified.items() if k != "digest_sha256"})
    assert verify_report(modified)[0] is False


def test_cli_writes_and_replays_report(tmp_path):
    output = tmp_path / "test-report.json"
    assert main(["run", "--cases", "14", "--output", str(output)]) == 0
    assert output.exists() and output.with_suffix(".html").exists()
    assert main(["verify-report", str(output)]) == 0
    assert "NO MODEL EXECUTED" in html_report(json.loads(output.read_text()))

class _FakeHTTPResponse:
    def __init__(self, content):
        self.content = content
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, amount):
        assert amount == 200_001
        return json.dumps(self.content).encode()


def test_ollama_local_provider_only_uses_loopback_and_schema(monkeypatch):
    import urllib.request
    from proofops.model_protocol import OllamaLocalProvider
    recorded = {}

    class Opener:
        def open(self, req, timeout):
            recorded["url"] = req.full_url
            recorded["timeout"] = timeout
            recorded["body"] = json.loads(req.data)
            return _FakeHTTPResponse({"message": {"content": '{"choice":"lookup_dns"}'},
                                      "done": True, "done_reason": "stop"})

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    provider = OllamaLocalProvider(timeout=15)
    result = provider.generate_step(build_request(()))
    assert parse_step(result) == ToolStep("lookup_dns", {})
    assert provider.calls == 1
    assert recorded["url"] == "http://127.0.0.1:11434/api/chat"
    assert recorded["timeout"] == 15
    assert recorded["body"]["stream"] is False
    assert recorded["body"]["format"]["type"] == "object"
    assert "lookup_dns" in recorded["body"]["format"]["properties"]["choice"]["enum"]
    assert recorded["body"]["format"]["additionalProperties"] is False
    assert recorded["body"]["model"] == "llama3.1:8b"
    assert "expected_action" not in str(recorded["body"])
    assert "case_id" not in str(recorded["body"])
    assert "API_KEY" not in json.dumps(recorded["body"])


def test_ollama_final_proposal_requires_second_schema_and_grounded_ids(monkeypatch):
    import urllib.request
    from proofops.model_protocol import OllamaLocalProvider
    recorded = []

    class Opener:
        def open(self, req, timeout):
            body = json.loads(req.data)
            recorded.append(body)
            result = ({"choice": "final_restore_dns"} if len(recorded) == 1 else {
                "root_cause": "Observed DNS drift", "explanation": "Backend healthy",
                "confidence": .78, "evidence_ids": ["topology", "dns"]})
            return _FakeHTTPResponse({"message": {"content": json.dumps(result)},
                                      "done": True, "done_reason": "stop"})

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    provider = OllamaLocalProvider()
    observations = COMPLETE_OLLAMA_EVIDENCE
    step = parse_step(provider.generate_step(build_request(observations)))
    assert step == FinalStep("restore_dns", "Observed DNS drift", "Backend healthy",
                             ("topology", "dns"), .78)
    assert provider.calls == 2
    assert recorded[1]["format"]["properties"]["evidence_ids"]["items"]["enum"] == [row["evidence_id"] for row in COMPLETE_OLLAMA_EVIDENCE]
    assert "unknown-id" not in recorded[1]["format"]["properties"]["evidence_ids"]["items"]["enum"]
    assert "done_reason" not in recorded[1]["messages"][-1]["content"]


def test_ollama_invalid_choice_rejected_and_report_explains_why(monkeypatch):
    import urllib.request
    from proofops.model_protocol import OllamaLocalProvider, run_local_case

    class Opener:
        def open(self, req, timeout):
            return _FakeHTTPResponse({"message": {"content": '{"choice":"run_shell"}'},
                                      "done": True, "done_reason": "stop"})

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    provider = OllamaLocalProvider()
    res = run_local_case(family="dns-drift", provider=provider)
    assert res["predicted_action"] == "invalid"
    assert res["tool_calls"] == 0
    assert res["error_detail"] == "Local model choice failed schema validation"
    assert res["provider_requests"] == 1
    assert res["repair_executed"] is False


def test_ollama_truncated_response_rejected(monkeypatch):
    import urllib.request
    from proofops.model_protocol import OllamaLocalProvider

    class Opener:
        def open(self, req, timeout):
            return _FakeHTTPResponse({"message": {"content": '{"choice":"lookup_dns"}'},
                                      "done": True, "done_reason": "length"})

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    with pytest.raises(InvalidModelStep, match="token limit"):
        OllamaLocalProvider().generate_step(build_request(()))


def test_ollama_does_not_repeat_already_observed_probe(monkeypatch):
    import urllib.request
    from proofops.model_protocol import OllamaLocalProvider
    observed = ({"evidence_id": "topology"},)
    captured = {}

    class Opener:
        def open(self, req, timeout):
            captured["body"] = json.loads(req.data)
            return _FakeHTTPResponse({"message": {"content": '{"choice":"customer_path"}'},
                                      "done": True, "done_reason": "stop"})

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    step = parse_step(OllamaLocalProvider().generate_step(build_request(observed)))
    assert step == ToolStep("customer_path", {})
    assert "topology" not in captured["body"]["format"]["properties"]["choice"]["enum"]


def test_ollama_final_with_invented_evidence_is_rejected(monkeypatch):
    import urllib.request
    from proofops.model_protocol import OllamaLocalProvider
    outputs = [json.dumps({"choice": "final_restore_dns"}),
               json.dumps({"root_cause": "DNS", "explanation": "Claim", "confidence": .9,
                           "evidence_ids": ["unknown-id"]})]

    class Opener:
        def open(self, req, timeout):
            return _FakeHTTPResponse({"message": {"content": outputs.pop(0)},
                                      "done": True, "done_reason": "stop"})

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    with pytest.raises(InvalidModelStep, match="unobserved or duplicate evidence"):
        OllamaLocalProvider().generate_step(build_request(COMPLETE_OLLAMA_EVIDENCE))


@pytest.mark.parametrize("model", ["llama3.1:70b", "muse-spark-1.3", "http://evil.org"])
def test_local_provider_disallows_unapproved_models(model):
    from proofops.model_protocol import OllamaLocalProvider
    with pytest.raises(ValueError, match="explicitly allowlisted"):
        OllamaLocalProvider(model)


def test_local_case_scripted_provider_does_not_use_docker_or_network():
    from proofops.model_protocol import run_local_case
    scripted = ScriptedStepProvider([
        to_wire(ToolStep("topology", {})),
        to_wire(ToolStep("customer_path", {})),
        to_wire(ToolStep("lookup_dns", {})),
        to_wire(ToolStep("inspect_gateway", {})),
        to_wire(ToolStep("probe_backend", {"backend": "backend-a"})),
        to_wire(FinalStep("restore_dns", "DNS fault", "Selected backend is healthy",
                          ("topology", "customer-path", "dns", "gateway", "backend-a"), .9)),
    ])
    result = run_local_case(family="dns-drift", provider=scripted)
    assert result["correct"] is True
    assert result["repair_executed"] is False
    assert result["no_cloud_api"] is True
    assert result["no_docker_execution"] is True
    assert scripted.calls == 6


def test_local_model_wrong_repair_is_not_counted_correct():
    from proofops.model_protocol import run_local_case
    provider = ScriptedStepProvider([
        to_wire(ToolStep("topology", {})),
        to_wire(FinalStep("restore_proxy", "Unproven cause", "Wrong action",
                          ("topology",), .99))
    ])
    result = run_local_case(family="dns-drift", provider=provider)
    assert result["correct"] is False
    assert result["unsafe"] is True
    assert result["repair_executed"] is False


def test_local_provider_failure_abstains_without_executing_repair():
    from proofops.model_protocol import run_local_case
    result = run_local_case(family="dns-drift", provider=ScriptedStepProvider([]))
    assert result["correct"] is False
    assert result["predicted_action"] == "invalid"
    assert result["error"] == "InvalidModelStep"
    assert result["error_detail"] == "Scripted response stream exhausted"
    assert result["repair_executed"] is False


def test_constrained_ollama_model_can_complete_full_readonly_dns_flow(monkeypatch):
    import urllib.request
    from proofops.model_protocol import OllamaLocalProvider, run_local_case
    names = ["topology", "customer_path", "lookup_dns", "inspect_gateway",
             "probe_backend_a", "final_restore_dns"]
    calls = []

    class Opener:
        def open(self, req, timeout):
            body = json.loads(req.data)
            calls.append(body)
            if len(calls) <= len(names):
                result = {"choice": names[len(calls) - 1]}
            else:
                result = {"root_cause": "DNS differs from configured gateway",
                          "explanation": "Customer path is down but selected backend is healthy",
                          "confidence": .82,
                          "evidence_ids": ["topology", "customer-path", "dns", "gateway", "backend-a"]}
            return _FakeHTTPResponse({"message": {"content": json.dumps(result)},
                                      "done": True, "done_reason": "stop"})

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    local = OllamaLocalProvider()
    result = run_local_case(family="dns-drift", provider=local)
    assert result["correct"] is True
    assert result["tool_calls"] == 5
    assert result["provider_requests"] == 7
    assert result["predicted_action"] == "restore_dns"
    assert result["repair_executed"] is False
    assert result["no_docker_execution"] is True
    assert all("expected_action" not in str(call) for call in calls)
    assert all("family" not in str(call) for call in calls)
    assert all("API_KEY" not in str(call) for call in calls)


def test_ollama_final_token_limit_uses_bounded_json_fallback(monkeypatch):
    """Regression: six read-only calls, schema final hits length, safe JSON retry."""
    import urllib.request
    from proofops.model_protocol import OllamaLocalProvider, run_local_case

    choices = ("topology", "customer_path", "lookup_dns", "inspect_gateway",
               "probe_backend_a", "probe_backend_b", "final_restore_dns")
    captured = []

    class Opener:
        def open(self, req, timeout):
            body = json.loads(req.data)
            captured.append(body)
            index = len(captured)
            if index <= len(choices):
                result = {"choice": choices[index - 1]}
                reason = "stop"
            elif index == 8:
                result = {"root_cause": "INCOMPLETE"}
                reason = "length"
            else:
                result = {"root_cause": "DNS record points to an incorrect IP",
                          "explanation": "DNS is wrong, while gateway and primary backend are healthy",
                          "confidence": 0.83, "evidence_ids": ["dns", "gateway", "backend-a"]}
                reason = "stop"
            return _FakeHTTPResponse({"message": {"content": json.dumps(result)},
                                      "done": True, "done_reason": reason})

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    provider = OllamaLocalProvider()
    result = run_local_case(family="dns-drift", provider=provider)
    assert result["correct"] is True
    assert result["unsafe"] is False
    assert result["tool_calls"] == 6
    assert result["provider_requests"] == 9
    assert result["token_limit_events"] == 1
    assert result["format_fallbacks"] == 1
    assert captured[7]["format"]["type"] == "object"
    assert captured[7]["options"]["num_predict"] == 512
    assert captured[8]["format"] == "json"
    assert captured[8]["options"]["num_predict"] == 1024
    assert set(json.loads(captured[8]["messages"][1]["content"])) == {
        "task", "selected_action", "observations", "allowed_evidence_ids"}
    assert "expected_action" not in json.dumps(captured)
    assert result["repair_executed"] is False


def test_ollama_final_token_limit_twice_fails_closed(monkeypatch):
    import urllib.request
    from proofops.model_protocol import OllamaLocalProvider, run_local_case
    calls = []

    class Opener:
        def open(self, req, timeout):
            body = json.loads(req.data)
            calls.append(body)
            if len(calls) == 1:
                return _FakeHTTPResponse({"message": {"content": '{"choice":"final_restore_dns"}'},
                                          "done": True, "done_reason": "stop"})
            return _FakeHTTPResponse({"message": {"content": '{"root_cause":"DNS"}'},
                                      "done": True, "done_reason": "length"})

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    provider = OllamaLocalProvider()
    tools = SyntheticReadOnlyTools(_make_case("dns-drift", "case-1", 98))
    for name, args in (
        ("topology", {}), ("customer_path", {}), ("lookup_dns", {}),
        ("inspect_gateway", {}), ("probe_backend", {"backend": "backend-a"}),
    ):
        tools.call(name, args)
    # Test the provider directly to ensure a failure can never become a tool request.
    with pytest.raises(InvalidModelStep, match="final fallback generation hit its token limit"):
        provider.generate_step(build_request(tools.observations))
    assert provider.calls == 3
    assert provider.token_limit_events == 2
    assert provider.format_fallbacks == 1
    assert calls[2]["format"] == "json"


def test_ollama_fallback_does_not_accept_fabricated_citation(monkeypatch):
    import urllib.request
    from proofops.model_protocol import OllamaLocalProvider
    calls = []

    class Opener:
        def open(self, req, timeout):
            body = json.loads(req.data)
            calls.append(body)
            if len(calls) == 1:
                result, reason = {"choice": "final_restore_dns"}, "stop"
            elif len(calls) == 2:
                result, reason = {}, "length"
            else:
                result, reason = {"root_cause": "DNS mismatch", "explanation": "Claim",
                                  "confidence": 0.99, "evidence_ids": ["imagined-proof"]}, "stop"
            return _FakeHTTPResponse({"message": {"content": json.dumps(result)},
                                      "done": True, "done_reason": reason})

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    provider = OllamaLocalProvider()
    with pytest.raises(InvalidModelStep, match="unobserved or duplicate"):
        provider.generate_step(build_request(COMPLETE_OLLAMA_EVIDENCE))
    assert provider.calls == 3
    assert provider.format_fallbacks == 1


def test_ollama_choice_is_not_prefilled_with_abstention(monkeypatch):
    """Regression: when no more probes are available, don't demo `final_none`."""
    import urllib.request
    from proofops.model_protocol import OllamaLocalProvider, REPAIR_PLAYBOOK, build_request

    tools = SyntheticReadOnlyTools(_make_case("dns-drift", "case-1", 98))
    for name, args in (
        ("topology", {}), ("customer_path", {}), ("lookup_dns", {}),
        ("inspect_gateway", {}), ("probe_backend", {"backend": "backend-a"}),
        ("probe_backend", {"backend": "backend-b"}),
    ):
        tools.call(name, args)
    captured = []

    class Opener:
        def open(self, req, timeout):
            payload = json.loads(req.data)
            captured.append(payload)
            result = ({"choice": "final_none"} if len(captured) == 1 else {
                "root_cause": "Cannot decide", "explanation": "Not enough evidence",
                "confidence": 0.12, "evidence_ids": ["dns"],
            })
            return _FakeHTTPResponse({"message": {"content": json.dumps(result)},
                                      "done": True, "done_reason": "stop"})

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    provider = OllamaLocalProvider()
    step = parse_step(provider.generate_step(build_request(tools.observations)))
    assert step.action == "none"  # A model abstention remains an abstention.
    assert provider.selection_history == ["final_none"]
    assert len(captured) == 2
    choices = captured[0]["format"]["properties"]["choice"]["enum"]
    assert set(choices) == {"final_none", "final_restore_dns", "final_restore_proxy", "final_failover"}
    message = json.loads(captured[0]["messages"][1]["content"])
    assert "output_example" not in message
    assert "expected_action" not in json.dumps(captured)
    assert "case_id" not in json.dumps(captured)
    assert REPAIR_PLAYBOOK in captured[0]["messages"][0]["content"]
    assert "correcting the app DNS record" in captured[0]["messages"][0]["content"]
    assert "multiple independent faults" in captured[0]["messages"][0]["content"]


def test_model_abstention_is_scored_as_missed_repair_without_override(monkeypatch):
    """Never rewrite an abstention into the expected repair inside model adapter."""
    import urllib.request
    from proofops.model_protocol import OllamaLocalProvider, run_local_case
    counter = 0

    class Opener:
        def open(self, req, timeout):
            nonlocal counter
            counter += 1
            result = ({"choice": "final_none"} if counter == 1 else {
                "root_cause": "Uncertain incident", "explanation": "Abstain",
                "confidence": 0.2, "evidence_ids": [],
            })
            return _FakeHTTPResponse({"message": {"content": json.dumps(result)},
                                      "done": True, "done_reason": "stop"})

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    report = run_local_case(family="dns-drift", provider=OllamaLocalProvider())
    assert report["correct"] is False
    assert report["unsafe"] is False
    assert report["missed_repair"] is True
    assert report["model_choices"] == ["final_none"]
    assert report["predicted_action"] == "none"
    assert report["repair_executed"] is False


def test_healthy_abstention_remains_correct(monkeypatch):
    import urllib.request
    from proofops.model_protocol import OllamaLocalProvider, run_local_case
    counter = 0

    class Opener:
        def open(self, req, timeout):
            nonlocal counter
            counter += 1
            result = ({"choice": "final_none"} if counter == 1 else {
                "root_cause": "No evidence of a fault", "explanation": "Abstain",
                "confidence": 0.8, "evidence_ids": [],
            })
            return _FakeHTTPResponse({"message": {"content": json.dumps(result)},
                                      "done": True, "done_reason": "stop"})

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    report = run_local_case(family="healthy", provider=OllamaLocalProvider())
    assert report["correct"] is True
    assert report["missed_repair"] is False
    assert report["unsafe"] is False


def test_explicit_local_qwen_models_are_allowlisted_but_remain_non_meta():
    from proofops.model_protocol import OllamaLocalProvider, run_local_case
    for name in ("qwen3.5:4b", "qwen3.5:9b"):
        provider = OllamaLocalProvider(name)
        assert provider.model == name
        result = run_local_case(
            family="dns-drift", model=name,
            provider=ScriptedStepProvider([
                to_wire(ToolStep("topology", {})),
                to_wire(ToolStep("customer_path", {})),
                to_wire(ToolStep("lookup_dns", {})),
                to_wire(ToolStep("inspect_gateway", {})),
                to_wire(ToolStep("probe_backend", {"backend": "backend-a"})),
                to_wire(FinalStep("restore_dns", "DNS fault", "Backend is healthy",
                                  ("topology", "customer-path", "dns", "gateway", "backend-a"), .8)),
            ]))
        assert result["correct"] is True
        assert result["model_family"] == "qwen"
        assert "not Meta" in result["assessment"]
        assert result["no_docker_execution"] is True
        assert result["repair_executed"] is False
    with pytest.raises(ValueError, match="explicitly allowlisted"):
        OllamaLocalProvider("qwen3.5:27b")


def test_qwen_ollama_payload_stays_local_and_schema_constrained(monkeypatch):
    import urllib.request
    from proofops.model_protocol import OllamaLocalProvider, build_request
    recorded = {}

    class Opener:
        def open(self, req, timeout):
            recorded["url"] = req.full_url
            recorded["body"] = json.loads(req.data)
            return _FakeHTTPResponse({"message": {"content": '{"choice":"lookup_dns"}'},
                                      "done": True, "done_reason": "stop"})

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: Opener())
    step = OllamaLocalProvider(model="qwen3.5:9b").generate_step(build_request(()))
    assert parse_step(step) == ToolStep("lookup_dns", {})
    assert recorded["url"] == "http://127.0.0.1:11434/api/chat"
    assert recorded["body"]["model"] == "qwen3.5:9b"
    assert recorded["body"]["format"]["type"] == "object"
    assert "expected_action" not in json.dumps(recorded["body"])
    assert "API_KEY" not in json.dumps(recorded["body"])


def test_old_local_llama_cli_remains_meta_only_and_new_local_model_allows_qwen(monkeypatch, tmp_path):
    from proofops.model_protocol import main
    import proofops.model_protocol as mp
    import argparse

    def fake_run_local_case(**kwargs):
        assert kwargs["model"] == "qwen3.5:9b"
        return {"model": kwargs["model"], "family": kwargs["family"],
                "predicted_action": "none", "expected_action": "none", "correct": True,
                "unsafe": False, "missed_repair": False, "tool_calls": 1,
                "provider_requests": 2, "error": None, "error_detail": None,
                "token_limit_events": 0, "format_fallbacks": 0,
                "model_choices": ["topology", "final_none"],
                "model_family": "qwen", "no_docker_execution": True,
                "repair_executed": False}

    monkeypatch.setattr(mp, "run_local_case", fake_run_local_case)
    with pytest.raises(SystemExit) as exc:
        main(["local-llama", "--model", "qwen3.5:9b"])
    assert exc.value.code == 2
    out = tmp_path / "local-qwen.json"
    assert main(["local-model", "--model", "qwen3.5:9b",
                 "--family", "healthy", "--output", str(out)]) == 0
    record = json.loads(out.read_text())
    assert record["model_family"] == "qwen"
    assert record["repair_executed"] is False
