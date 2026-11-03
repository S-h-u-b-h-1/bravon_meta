"""No live Meta calls in CI: tests validate harness boundaries and the tool protocol."""
import json
from types import SimpleNamespace as NS

import pytest

from proofops.frontier_eval import (
    CASES, SafeSyntheticTools, validate_report, estimate_cost,
    investigate_case, short_error, check_api, main,
)


def test_read_only_tools_reveal_observations_but_not_scoring_labels():
    tools = SafeSyntheticTools(CASES[0].config)
    dns = tools.call("lookup_dns", {})
    assert dns == {"evidence_id": "dns", "hostname": "app.proofops.test", "resolved_target": "unknown-target"}
    assert "expected" not in dns
    assert "restore_dns" not in json.dumps(dns)
    assert tools.evidence_ids == {"dns"}


def test_untrusted_tool_names_and_arguments_are_rejected():
    tools = SafeSyntheticTools(CASES[0].config)
    for name, args in (("shell", {"cmd": "rm -rf /"}), ("lookup_dns", {"secret": "value"}),
                       ("probe_backend", {"backend": "../../etc/passwd"}), ("probe_backend", {})):
        with pytest.raises(ValueError):
            tools.call(name, args)
    assert tools.evidence_ids == set()


def test_hard_cases_have_no_safe_single_action():
    assert {c.id: c.expected for c in CASES}["compound_fault"] == "none"
    assert {c.id: c.expected for c in CASES}["no_standby"] == "none"


def test_report_rejects_fabricated_evidence_and_unsafe_action():
    report = {
        "root_cause": "Record incorrect", "action": "restore_dns", "explanation": "Observed drift",
        "evidence_ids": ["dns"], "confidence": 0.8,
    }
    validate_report(report, {"dns"})
    with pytest.raises(ValueError, match="evidence"):
        validate_report(report, {"gateway"})
    with pytest.raises(ValueError, match="action"):
        validate_report({**report, "action": "execute_shell"}, {"dns"})
    with pytest.raises(ValueError, match="Confidence"):
        validate_report({**report, "confidence": True}, {"dns"})


def test_cost_estimate_is_usd_not_fabricated_accuracy():
    assert estimate_cost("muse-spark-1.3", 1_000_000, 1_000_000) == 5.5
    assert estimate_cost("muse-wonder-1.0", 1_000_000, 1_000_000) == 24.0


class ScriptedResponses:
    """Fake Responses API: 1 tool-use step, then valid final JSON."""
    def __init__(self):
        self.calls = []
    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return NS(id="resp_a", output=[NS(type="function_call", name="lookup_dns",
                          arguments="{}", call_id="call_one")], output_text="",
                      usage=NS(input_tokens=100, output_tokens=50))
        assert kwargs["previous_response_id"] == "resp_a"
        assert kwargs["input"] == [{"type": "function_call_output", "call_id": "call_one",
                                   "output": '{"evidence_id": "dns", "hostname": "app.proofops.test", "resolved_target": "unknown-target"}'}]
        return NS(id="resp_b", output=[], usage=NS(input_tokens=60, output_tokens=20),
                  output_text=json.dumps({"root_cause": "DNS drift", "action": "restore_dns",
                                          "explanation": "The observed DNS record is unknown-target",
                                          "evidence_ids": ["dns"], "confidence": 0.8}))


def test_responses_tool_roundtrip_and_grounded_answer():
    client = NS(responses=ScriptedResponses())
    trial = investigate_case(client, "muse-spark-1.3", CASES[0])
    assert trial["correct_action"] is True
    assert trial["source"] == "live-meta-response"
    assert trial["inspection_count"] == 1
    assert trial["adequate_probing"] is False  # one inspection is not enough for the benchmark criterion
    assert trial["input_tokens"] == 160
    assert trial["output_tokens"] == 70
    assert client.responses.calls[0]["text"]["format"]["type"] == "json_schema"


def test_minimal_connectivity_check_uses_responses_and_no_storage():
    class Fake:
        def __init__(self): self.args = None
        def create(self, **kwargs):
            self.args = kwargs
            return NS(output=[NS(type="message")], output_text="READY")
    responses = Fake()
    state = check_api(NS(responses=responses), "muse-spark-1.3")
    assert state["received_text"]
    assert responses.args["store"] is False


def test_dry_run_never_loads_or_calls_meta(monkeypatch, capsys):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    assert main([]) == 0
    assert "no network calls" in capsys.readouterr().out


def test_short_error_suppresses_provider_body():
    secret = "superprivate"
    error = Exception("Authorization: Bearer " + secret)
    assert secret not in short_error(error)
