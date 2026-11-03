"""Offline, deterministic Immortality tests; NO Docker daemon or Meta requests."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from proofops.immortality import (
    SCHEMA, MODEL, compile_antibody, digest, evaluate, main,
    nightmare_plan, preview, topology_for_slot, validate_antibody,
    valid_transfer_digest,
)
from proofops.model_protocol import WireInvestigator
from proofops.real_lab import CONFIRM_PHRASE
from test_hosted_muse_matrix import _lab, _model


@pytest.fixture(params=[
    ("dns-drift", "restore_dns"),
    ("proxy-misroute", "restore_proxy"),
    ("backend-outage", "failover"),
])
def recovered(monkeypatch, tmp_path, request):
    scenario, action = request.param
    lab, runner = _lab(tmp_path)
    try:
        lab.start()
        lab.inject(scenario)
        provider, calls = _model(monkeypatch, action)
        lab.investigate(agent=WireInvestigator(provider), label=provider.source_label)
        tested = lab.verify()
        report = lab.repair(
            approved=True, expected_revision=tested["revision"],
            confirmation=CONFIRM_PHRASE,
        )
        assert len(calls) == 8
    finally:
        lab.stop()
    assert not runner.projects
    return report


def test_antibodies_from_three_verified_recoveries_have_no_source_ips(recovered):
    policy = compile_antibody(recovered)
    assert policy["schema"] == SCHEMA
    assert policy["origin"]["model"] == MODEL
    assert len(policy["policy_digest"]) == 64
    assert validate_antibody(policy)[0] == recovered["active_incident"]["raw_action"]
    raw = json.dumps(policy)
    assert "10.223.120." not in raw
    assert "Fixture-only fault hypothesis" not in raw
    assert "PRIVATE" not in raw


def test_tampered_recovery_never_compiles(recovered):
    changed = deepcopy(recovered)
    changed["active_incident"]["proof"]["action"] = "restore_proxy" if (
        recovered["active_incident"]["raw_action"] != "restore_proxy") else "restore_dns"
    with pytest.raises(ValueError, match="recovered incident"):
        compile_antibody(changed)


def test_missing_original_model_citation_never_compiles(recovered):
    changed = deepcopy(recovered)
    changed["active_incident"]["investigation"]["proposal"]["evidence_ids"] = []
    with pytest.raises(ValueError):
        compile_antibody(changed)


def test_policy_semantics_cannot_be_edited_or_replaced(recovered):
    policy = compile_antibody(recovered)
    altered = deepcopy(policy)
    altered["rule"] = "Execute arbitrary command"
    altered["policy_digest"] = digest({
        k: v for k, v in altered.items() if k != "policy_digest"
    })
    with pytest.raises(ValueError, match="semantics"):
        validate_antibody(altered)
    altered = deepcopy(policy)
    altered["origin"]["model"] = "unverified-model"
    altered["policy_digest"] = digest({
        k: v for k, v in altered.items() if k != "policy_digest"
    })
    with pytest.raises(ValueError, match="provenance"):
        validate_antibody(altered)


def test_cross_system_bounded_nightmares_block_bad_allow_good(recovered):
    policy = compile_antibody(recovered)
    a = topology_for_slot(120)
    b = topology_for_slot(150)
    assert a["gateway_ip"] != b["gateway_ip"]
    proposals = nightmare_plan(policy, b)
    assert [p["expected"] for p in proposals] == ["BLOCK", "ALLOW"]
    assert [p["assessment"]["decision"] for p in proposals] == ["BLOCK", "ALLOW"]
    assert proposals[0]["candidate"] != proposals[1]["candidate"]
    # No source-system IP embedded in either destination policy evaluation.
    assert all("10.223.120." not in json.dumps(p) for p in proposals)


def test_dns_antibody_does_not_block_valid_unrelated_route_change(monkeypatch, tmp_path):
    lab, _ = _lab(tmp_path)
    try:
        lab.start()
        lab.inject("dns-drift")
        provider, _ = _model(monkeypatch, "restore_dns")
        lab.investigate(agent=WireInvestigator(provider), label=provider.source_label)
        verified = lab.verify()
        recovered = lab.repair(
            approved=True, expected_revision=verified["revision"],
            confirmation=CONFIRM_PHRASE,
        )
    finally:
        lab.stop()
    antibody = compile_antibody(recovered)
    b = topology_for_slot(150)
    # Legitimate route to backend B is allowed when DNS still matches B gateway.
    allowed = evaluate(
        antibody, b, {"dns_answer_ip": b["gateway_ip"],
                      "upstream_ip": b["backends"]["backend-b"]["ip"]},
    )
    blocked = evaluate(
        antibody, b, {"dns_answer_ip": "10.223.150.99",
                      "upstream_ip": b["backends"]["backend-b"]["ip"]},
    )
    assert allowed["decision"] == "ALLOW"
    assert blocked["decision"] == "BLOCK"


def test_failover_antibody_blocks_known_unhealthy_destination(recovered):
    policy = compile_antibody(recovered)
    if policy["family"] != "selected-backend-healthy":
        pytest.skip("Applies to failover-only origin")
    b = topology_for_slot(150)
    b["backends"]["backend-a"]["healthy"] = False
    a_ip = b["backends"]["backend-a"]["ip"]
    b_ip = b["backends"]["backend-b"]["ip"]
    assert evaluate(policy, b, {"dns_answer_ip": b["gateway_ip"],
                               "upstream_ip": a_ip})["decision"] == "BLOCK"
    assert evaluate(policy, b, {"dns_answer_ip": b["gateway_ip"],
                               "upstream_ip": b_ip})["decision"] == "ALLOW"


def test_untrusted_topology_and_bad_candidate_fail_closed(recovered):
    policy = compile_antibody(recovered)
    b = topology_for_slot(150)
    b["backends"]["backend-a"]["healthy"] = "maybe"
    with pytest.raises(ValueError, match="measured health"):
        nightmare_plan(policy, b)
    fixed = topology_for_slot(150)
    with pytest.raises(ValueError, match="Candidate"):
        evaluate(policy, fixed, {"command": "rm -rf /"})
    with pytest.raises(ValueError, match="Invalid IPv4"):
        evaluate(policy, fixed, {"dns_answer_ip": "not-an-ip",
                                 "upstream_ip": "10.223.150.21"})


def test_read_only_preview_and_stale_network_refusal(recovered, tmp_path, capsys):
    report = preview(recovered, destination_slot=150)
    assert report["mode"] == "SYNTHETIC_POLICY_PREVIEW_ONLY"
    assert report["status"] == "policy-evaluated"
    assert report["active_destination_remained_healthy"] is None
    assert valid_transfer_digest(report)
    with pytest.raises(ValueError, match="distinct network"):
        preview(recovered, destination_slot=120)
    source_file = tmp_path / "source.json"
    source_file.write_text(json.dumps(recovered))
    path = tmp_path / "preview.json"
    assert main(["preview", "--source-report", str(source_file),
                 "--output", str(path)]) == 0
    assert path.exists()
    assert main(["preview", "--source-report", str(source_file),
                 "--output", str(path)]) == 2
    assert valid_transfer_digest(json.loads(path.read_text()))
    assert "refused" in capsys.readouterr().err.lower()


def test_mutated_transfer_digest_detected(recovered):
    record = preview(recovered)
    altered = deepcopy(record)
    altered["cases"][0]["decision"] = "ALLOW"
    assert not valid_transfer_digest(altered)
