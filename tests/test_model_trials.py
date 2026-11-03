"""The model-scorecard is offline by default and makes no repair decisions."""
import json
from pathlib import Path

import pytest

from proofops.evidence_gate import assess_proposal
from proofops.investigation import FinalStep, ReferenceInvestigator
from proofops.model_protocol import ScriptedStepProvider, to_wire
from proofops.openrouter_free import FreeModelProvider, run_synthetic_case
from proofops.model_trials import (CONFIRMATION, build_suite, main, render_html,
                                  summarize, save_suite, SUITE_SCHEMA)


def sample_case(family, action):
    ids = ("topology", "customer-path", "dns", "gateway", "backend-a", "backend-b")
    steps = [to_wire(x) for x in ReferenceInvestigator.PLAN]
    steps.append(to_wire(FinalStep(action, "Example root cause", "No repair executed", ids, 0.5)))
    return run_synthetic_case(family=family, provider=ScriptedStepProvider(steps))


def test_preview_no_key_network_or_docker(monkeypatch, capsys):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(FreeModelProvider, "__init__", lambda self, **kw: pytest.fail("model should not be constructed"))
    assert main(["preview"]) == 0
    out = capsys.readouterr().out
    assert "NO NETWORK, NO DOCKER" in out
    assert "30 requests" in out


def test_wrong_confirmation_prevents_any_model_calls(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    monkeypatch.setattr(FreeModelProvider, "__init__", lambda self, **kw: pytest.fail("no model expected"))
    with pytest.raises(SystemExit) as err:
        main(["run", "--confirm", "YES"])
    assert err.value.code == 2


def test_render_preserves_wrong_action_and_gate_rejection():
    suite = build_suite([sample_case("dns-drift", "restore_proxy"),
                         sample_case("healthy", "none"),
                         sample_case("compound-dns-proxy", "restore_dns")])
    assert suite["schema"] == SUITE_SCHEMA
    assert suite["source_mode"] == "offline-mock"
    assert suite["summary"]["correct"] == 1
    assert suite["summary"]["unsafe_proposals"] == 2
    assert suite["summary"]["unsafe_proposals_blocked_by_evidence_gate"] == 2
    assert suite["summary"]["repair_executed"] is False
    html = render_html(suite)
    assert "OFFLINE MOCK / NOT A REAL MODEL RESULT" in html
    assert "1/3" in html
    assert "restore_proxy" in html
    assert "compound dns proxy" in html.lower()
    assert "No Docker services or production systems are modified" in html


def test_scorecard_escapes_untrusted_model_text():
    item = sample_case("dns-drift", "restore_dns")
    item["trace"][-1]["explanation"] = '<img src=x onerror="alert(1)">'
    item["evidence_gate"]["reason"] = "<iframe>"
    html = render_html(build_suite([item]))
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in html
    assert "&lt;iframe&gt;" in html
    assert '<img src=x onerror="alert(1)">' not in html
    assert "<iframe>" not in html
    assert 'Content-Security-Policy' in html


def test_render_from_existing_reports_offline(tmp_path, monkeypatch):
    single = sample_case("healthy", "none")
    source = tmp_path / "single.json"
    source.write_text(json.dumps(single), encoding="utf-8")
    monkeypatch.setattr(FreeModelProvider, "__init__", lambda self, **kw: pytest.fail("no network expected"))
    dest = tmp_path / "score.json"
    assert main(["render", str(source), "--output", str(dest)]) == 0
    assert dest.exists()
    assert dest.with_suffix(".html").exists()
    assert json.loads(dest.read_text())["summary"]["correct"] == 1


def test_suite_rejects_duplicate_family_and_unsupported_report():
    one = sample_case("healthy", "none")
    with pytest.raises(ValueError, match="distinct"):
        build_suite([one, one])
    with pytest.raises(ValueError, match="schema"):
        summarize([{"schema": "made-up"}])


def test_live_trial_aggregates_up_to_three_cases_without_real_calls(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-secret")
    constructed = []
    class FakeFreeProvider:
        def __init__(self, *, request_budget=10, progress=None):
            constructed.append(request_budget)
            self.calls = 7
            self.model = FreeModelProvider.MODEL
            self.progress = progress
            if self.progress:
                self.progress("mocked local request")
    def fake_case(*, family, provider):
        assert isinstance(provider, FakeFreeProvider)
        action = {"dns-drift": "restore_dns", "healthy": "none", "compound-dns-proxy": "none"}[family]
        r = sample_case(family, action)
        r.update(provider_model=FreeModelProvider.MODEL, model_calls=7,
                 evaluation_type="EXTERNAL REAL MODEL, SYNTHETIC EVIDENCE (test simulation)")
        return r
    monkeypatch.setattr('proofops.model_trials.FreeModelProvider', FakeFreeProvider)
    monkeypatch.setattr('proofops.model_trials.run_synthetic_case', fake_case)
    output = tmp_path / 'suite.json'
    assert main(["run", "--confirm", CONFIRMATION, "--output", str(output)]) == 0
    saved = json.loads(output.read_text())
    assert saved['summary']['cases'] == 3
    assert saved['summary']['correct'] == 3
    assert saved['summary']['model_requests'] == 21
    assert saved['status'] == 'complete'
    assert constructed == [10, 10, 10]
    assert "private-test-secret" not in output.read_text()
    assert "private-test-secret" not in output.with_suffix('.html').read_text()


def test_partial_run_stops_after_error_and_saves_report(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-secret")
    class FakeFreeProvider:
        def __init__(self, *, request_budget=10, progress=None):
            self.calls = 2
            self.model = FreeModelProvider.MODEL
    def fake_case(*, family, provider):
        r = sample_case(family, 'none')
        r['error'] = 'InvalidModelStep'
        r['error_detail'] = 'Free model HTTP 429'
        return r
    monkeypatch.setattr('proofops.model_trials.FreeModelProvider', FakeFreeProvider)
    monkeypatch.setattr('proofops.model_trials.run_synthetic_case', fake_case)
    output = tmp_path / 'partial.json'
    assert main(['run', '--confirm', CONFIRMATION, '--output', str(output)]) == 2
    saved = json.loads(output.read_text())
    assert saved['status'] == 'partial'
    assert saved['summary']['cases'] == 1
    preview_html = output.with_suffix('.html').read_text()
    assert 'Partial run' in preview_html
    assert 'Incomplete benchmark' in preview_html
    assert '<b>—</b>' in preview_html


def test_free_provider_request_budget_enforced_before_network(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-secret")
    p = FreeModelProvider(request_budget=1)
    p.calls = 1
    from proofops.model_protocol import build_request, InvalidModelStep
    with pytest.raises(InvalidModelStep, match='cap'):
        p.generate_step(build_request(()))
    with pytest.raises(ValueError, match="budget"):
        FreeModelProvider(request_budget=11)
    with pytest.raises(ValueError, match="budget"):
        FreeModelProvider(request_budget=True)


def test_scorecard_shows_reasoning_and_truncation_diagnostics():
    result = sample_case("dns-drift", "restore_dns")
    result.update(reasoning_tokens=100, finish_reasons=["stop", "length"],
                  token_limit_events=1, request_phases=["tool selection", "final explanation"],
                  reasoning_disabled_requested=True)
    html = render_html(build_suite([result]))
    assert "100 reasoning tokens" in html
    assert "Finish reasons:" in html and "length" in html
    assert "Reasoning off requested: True" in html
    assert "Token cap events: 1" in html


def test_scorecard_displays_compact_choice_recovery_and_escapes_failed_reply_preview():
    result = sample_case("dns-drift", "restore_dns")
    result.update(compact_choice_recoveries=1, invalid_reply_previews=[{
        "phase": "tool selection", "reason": "malformed",
        "excerpt": '<img src=x onerror="alert(1)">',
    }])
    html = render_html(build_suite([result]))
    assert "Exact-choice format recoveries: 1" in html
    assert "Rejected reply samples" in html
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in html
    assert '<img src=x onerror="alert(1)">' not in html


def test_correct_raw_action_can_be_unqualified_without_evidence():
    from proofops.investigation import ToolStep
    steps = [
        to_wire(ToolStep("topology", {})),
        to_wire(ToolStep("lookup_dns", {})),
        to_wire(ToolStep("customer_path", {})),
        to_wire(FinalStep("restore_dns", "DNS mismatch", "Incomplete evidence",
                          ("topology", "dns", "customer-path"), 0.8)),
    ]
    item = run_synthetic_case(family="dns-drift", provider=ScriptedStepProvider(steps))
    assert item["correct"] is True
    assert item["unsafe_proposal"] is False
    assert item["evidence_gate"]["allowed"] is False
    suite = build_suite([item])
    summary = suite["summary"]
    assert summary["correct"] == 1
    assert summary["gate_qualified_correct"] == 0
    assert summary["gate_rejections"] == 1
    assert summary["unsafe_proposals_blocked_by_evidence_gate"] == 0
    html = render_html(suite)
    assert "Correct action · missing proof" in html
    assert "GATE-QUALIFIED" in html
    assert "Includes missing evidence" in html


def test_citation_gap_is_visible_and_html_escaped():
    item = sample_case("dns-drift", "restore_dns")
    assert item["evidence_gap"]["missing_probe_ids"] == []
    item["evidence_gap"]["missing_citation_ids"] = ["<script>"]
    html = render_html(build_suite([item]))
    assert "Missing model citations" in html
    assert "&lt;script&gt;" in html
    assert "<script>" not in html
