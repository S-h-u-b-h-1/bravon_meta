"""Offline, no-network jury receipt security and privacy regression tests."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from proofops import jury_receipt
from proofops.immortality import MODEL, digest
from test_immortality_audit import simulated_transfer
from test_immortality_docker import dns_recovery


def summary():
    return {
        "incident_id": "incident-1",
        "source": MODEL, "scenario": "dns-drift",
        "model_action": "restore_dns", "promoted_action": "restore_dns",
        "outcome": "recovered", "model_correct": True, "gate_allowed": True,
        "sandbox_verified": True, "active_recovered": True,
        "integrity_errors": [], "missing_observations": [],
        "missing_citations": [], "hosted_requests": 7,
        "tool_calls": 6, "cited_ids": ["dns", "topology", "health"],
    }


def audit():
    return {
        "verdict": "STRUCTURALLY_CONSISTENT_CONTROLLER_REPORT",
        "mode": "REAL_ISOLATED_DOCKER",
        "origin_model": MODEL, "origin_action": "restore_dns",
        "policy_family": "dns-gateway-binding", "destination": "B",
        "dangerous_case": {"decision":"BLOCK", "failed_docker_checks":["dns-record","e2e"]},
        "legitimate_case": {"decision":"ALLOW", "all_five_docker_checks_passed":True},
        "active_destination_preserved":True, "cleanup_recorded":True,
        "source_recovery_digest":"a"*64, "transfer_report_digest":"b"*64,
    }


def accepted(monkeypatch, source_score=None, transfer_score=None):
    monkeypatch.setattr(jury_receipt, "audit_transfer", lambda *_: (
        audit() if transfer_score is None else transfer_score
    ))
    monkeypatch.setattr(jury_receipt, "score_report", lambda *_args, **_kwargs: (
        summary() if source_score is None else source_score
    ))


def test_receipt_exports_only_fixed_non_sensitive_properties(monkeypatch):
    accepted(monkeypatch)
    source = {"private_ip": "10.223.120.10", "secret": "MODEL_API_KEY=never-export"}
    transfer = {"private_path": "/tmp/bravon-private-path-fixture"}
    output = jury_receipt.build_receipt(source, transfer)
    assert set(output) == {
        "schema", "evidence_level", "source", "transfer", "links",
        "limitations", "content_digest"
    }
    assert output["source"]["hosted_requests"] == 7
    assert output["source"]["model"] == MODEL
    assert output["transfer"]["dangerous_policy"] == "BLOCK"
    assert output["transfer"]["legitimate_policy"] == "ALLOW"
    raw = json.dumps(output)
    for phrase in ("MODEL_API_KEY", "never-export", "/Users", "10.223.", "prompt", "raw_log"):
        assert phrase not in raw
    assert output["content_digest"] == digest({
        k: v for k, v in output.items() if k != "content_digest"
    })
    assert len(raw) < 64_000


@pytest.mark.parametrize("field, replacement", [
    ("gate_allowed", False),
    ("active_recovered", False),
    ("sandbox_verified", False),
    ("hosted_requests", 0),
    ("hosted_requests", 99),
    ("model_action", "restore_proxy"),
    ("source", "unapproved-model"),
])
def test_receipt_refuses_unqualified_source(monkeypatch, field, replacement):
    value=summary()
    value[field]=replacement
    accepted(monkeypatch,source_score=value)
    with pytest.raises(ValueError):
        jury_receipt.build_receipt({}, {})


def test_receipt_refuses_mismatched_investigation(monkeypatch):
    scores = [summary(), {**summary(), "incident_id": "incident-2"}]
    monkeypatch.setattr(jury_receipt, "audit_transfer", lambda *_: audit())
    monkeypatch.setattr(jury_receipt, "score_report", lambda *_args, **_kwargs: scores.pop(0))
    with pytest.raises(ValueError, match="does not match"):
        jury_receipt.build_receipt({}, {}, {})


@pytest.mark.parametrize("field, replacement", [
    ("mode","SIMULATED_DOCKER_TEST"),
    ("cleanup_recorded",False),
    ("policy_family","proxy-declared-backend"),
])
def test_receipt_refuses_unqualified_destination(monkeypatch, field, replacement):
    value=audit()
    value[field]=replacement
    accepted(monkeypatch,transfer_score=value)
    with pytest.raises(ValueError):
        jury_receipt.build_receipt({}, {})


def test_actual_offline_auditor_rejects_simulated_docker_fixture(
    dns_recovery, simulated_transfer
):
    """A successful *fake Docker* run cannot become a jury receipt."""
    with pytest.raises(ValueError, match="Real isolated Docker"):
        jury_receipt.build_receipt(dns_recovery, simulated_transfer)


def test_cli_refuses_simulated_report_before_creating_receipt(
    dns_recovery, simulated_transfer, tmp_path
):
    source=tmp_path / "source.json"
    transfer=tmp_path / "simulated.json"
    target=tmp_path / "jury.json"
    source.write_text(json.dumps(dns_recovery), encoding="utf-8")
    transfer.write_text(json.dumps(simulated_transfer), encoding="utf-8")
    result = jury_receipt.main([
        "--source-report", str(source),
        "--transfer-report", str(transfer),
        "--output", str(target),
    ])
    assert result == 2
    assert not target.exists()


def test_cli_refuses_symlinked_input_and_does_not_create_output(tmp_path):
    original=tmp_path / "source.json"
    original.write_text("{}", encoding="utf-8")
    symlink=tmp_path / "link.json"
    symlink.symlink_to(original)
    transfer=tmp_path / "other.json"
    transfer.write_text("{}", encoding="utf-8")
    target=tmp_path / "receipt.json"
    assert jury_receipt.main([
        "--source-report",str(symlink),
        "--transfer-report",str(transfer),
        "--output",str(target),
    ]) == 2
    assert not target.exists()


def test_export_never_overwrites_existing_file(monkeypatch,tmp_path):
    accepted(monkeypatch)
    path=tmp_path / "already.json"
    path.write_text("NEVER OVERWRITE", encoding="utf-8")
    report=jury_receipt.build_receipt({}, {})
    with pytest.raises(ValueError, match="new file"):
        jury_receipt.write_private(path,report)
    assert path.read_text(encoding="utf-8") == "NEVER OVERWRITE"
