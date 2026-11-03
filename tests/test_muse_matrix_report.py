"""The offline scorer must distinguish model accuracy from repair-safety evidence."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from proofops.model_protocol import WireInvestigator
from proofops.muse_matrix_report import main, score_report
from proofops.real_lab import CONFIRM_PHRASE
from test_hosted_muse_matrix import _lab, _model


@pytest.mark.parametrize("scenario,action", [
    ("dns-drift", "restore_dns"),
    ("proxy-misroute", "restore_proxy"),
    ("backend-outage", "failover"),
])
def test_offline_report_validates_complete_fake_lifecycle(
    monkeypatch, tmp_path, scenario, action,
):
    lab, _runner = _lab(tmp_path)
    try:
        lab.start()
        lab.inject(scenario)
        provider, calls = _model(monkeypatch, action)
        decided = lab.investigate(agent=WireInvestigator(provider), label=provider.source_label)

        diagnosis = score_report(decided, required_source=provider.source_label)
        assert diagnosis["model_correct"] is True
        assert diagnosis["gate_allowed"] is True
        assert diagnosis["outcome"] == "gate_accepted"
        assert not diagnosis["sandbox_verified"]
        assert not diagnosis["active_recovered"]
        assert diagnosis["integrity_errors"] == []

        verified = lab.verify()
        clone = score_report(verified, required_source=provider.source_label)
        assert clone["outcome"] == "sandbox_verified"
        assert clone["sandbox_verified"] is True
        assert clone["active_recovered"] is False
        assert clone["integrity_errors"] == []

        final = lab.repair(
            approved=True, expected_revision=verified["revision"],
            confirmation=CONFIRM_PHRASE,
        )
        calls_before_score = len(calls)
        report = score_report(final, required_source=provider.source_label)
        assert report["outcome"] == "recovered"
        assert report["model_correct"] is True
        assert report["sandbox_verified"] is True
        assert report["active_recovered"] is True
        assert report["integrity_errors"] == []
        assert report["missing_citations"] == []
        assert len(calls) == calls_before_score, "Scorer must not call hosted model"
    finally:
        lab.stop()


def test_wrong_model_decision_scores_as_blocked_not_success(monkeypatch, tmp_path):
    lab, _ = _lab(tmp_path)
    try:
        lab.start()
        lab.inject("dns-drift")
        provider, _calls = _model(monkeypatch, "restore_proxy")
        decided = lab.investigate(agent=WireInvestigator(provider), label=provider.source_label)
        report = score_report(decided)
        assert report["model_action"] == "restore_proxy"
        assert report["expected_action"] == "restore_dns"
        assert report["model_correct"] is False
        assert report["blocked_wrong_repair"] is True
        assert report["gate_allowed"] is False
        assert report["outcome"] == "rejected"
        assert report["integrity_errors"] == []
    finally:
        lab.stop()


def test_wrong_action_promoted_is_flagged_as_safety_violation(monkeypatch, tmp_path):
    lab, _ = _lab(tmp_path)
    try:
        lab.start()
        lab.inject("dns-drift")
        provider, _calls = _model(monkeypatch, "restore_proxy")
        rejected = lab.investigate(
            agent=WireInvestigator(provider), label=provider.source_label,
        )
        forged = deepcopy(rejected)
        forged["active_incident"]["action"] = "restore_proxy"
        forged["active_incident"]["evidence_gate"]["allowed"] = True
        scored = score_report(forged)
        assert scored["model_correct"] is False
        assert "Incorrect repair promoted for known injected fault" in scored["integrity_errors"]
        assert scored["active_recovered"] is False
    finally:
        lab.stop()


def test_tampered_recovery_proof_fails_integrity_check(monkeypatch, tmp_path):
    lab, _ = _lab(tmp_path)
    try:
        lab.start()
        lab.inject("dns-drift")
        provider, _calls = _model(monkeypatch, "restore_dns")
        lab.investigate(agent=WireInvestigator(provider), label=provider.source_label)
        verified = lab.verify()
        recovered = lab.repair(
            approved=True, expected_revision=verified["revision"],
            confirmation=CONFIRM_PHRASE,
        )

        altered = deepcopy(recovered)
        altered["active_incident"]["proof"]["action"] = "restore_proxy"
        score = score_report(altered)
        assert score["active_recovered"] is False
        assert "Active recovery proof inconsistent or invalid" in score["integrity_errors"]

        path = tmp_path / "altered.json"
        path.write_text(json.dumps(altered), encoding="utf-8")
        assert main([str(path)]) == 3
    finally:
        lab.stop()


def test_cli_json_summary_and_provenance_rejection(monkeypatch, tmp_path, capsys):
    lab, _ = _lab(tmp_path)
    try:
        lab.start()
        lab.inject("proxy-misroute")
        provider, _calls = _model(monkeypatch, "restore_proxy")
        decided = lab.investigate(agent=WireInvestigator(provider), label=provider.source_label)
        saved = tmp_path / "investigation.json"
        saved.write_text(json.dumps(decided), encoding="utf-8")

        assert main(["--json", "--require-source", provider.source_label, str(saved)]) == 0
        printed = json.loads(capsys.readouterr().out)
        assert printed["report_schema"] == "bravon.muse-offline-matrix.v1"
        assert printed["summary"]["total"] == 1
        assert printed["summary"]["model_correct"] == 1
        assert printed["summary"]["recovered"] == 0

        assert main(["--require-source", "local-model:wrong", str(saved)]) == 2
        assert "source" in capsys.readouterr().err
    finally:
        lab.stop()
