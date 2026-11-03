"""Offline evidence audit regression tests using fake Meta and Docker only.

No actual inference, network, customer infrastructure, or external publishing.
"""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from proofops.immortality import digest, valid_transfer_digest
from proofops.immortality_audit import (
    AUDIT_SCHEMA, audit_transfer, candidate_export, main,
)
from proofops.immortality_docker import run_transfer
from test_immortality_docker import dns_recovery  # pytest fixture
from test_real_lab import FakeDockerRunner


@pytest.fixture
def simulated_transfer(dns_recovery, tmp_path):
    result = run_transfer(
        dns_recovery, slot=150, root=tmp_path / "only-fake-docker",
        runner=FakeDockerRunner(),
    )
    assert result["mode"] == "SIMULATED_DOCKER_TEST"
    assert result["status"] == "verified-experimental-transfer"
    return result


def _reseal(obj):
    obj["report_digest"] = digest({
        k: v for k, v in obj.items() if k != "report_digest"
    })


def test_auditor_checks_all_reported_fake_docker_cases(
    dns_recovery, simulated_transfer
):
    summary = audit_transfer(dns_recovery, simulated_transfer, allow_simulated=True)
    assert summary["audit_schema"] == AUDIT_SCHEMA
    assert summary["mode"] == "SIMULATED_DOCKER_TEST"
    assert summary["verdict"] == "STRUCTURALLY_CONSISTENT_CONTROLLER_REPORT"
    assert summary["dangerous_case"]["failed_docker_checks"] == ["dns-record", "e2e"]
    assert summary["legitimate_case"]["all_five_docker_checks_passed"] is True
    assert summary["cleanup_recorded"] is True


def test_fake_docker_cannot_be_published_as_real(dns_recovery, simulated_transfer):
    with pytest.raises(ValueError, match="Real isolated Docker"):
        audit_transfer(dns_recovery, simulated_transfer)
    with pytest.raises(ValueError, match="Real isolated Docker"):
        candidate_export(dns_recovery, simulated_transfer)


def test_unsealed_changed_result_is_rejected(dns_recovery, simulated_transfer):
    altered = deepcopy(simulated_transfer)
    altered["cases"][0]["clone_after"][0]["passed"] = not (
        altered["cases"][0]["clone_after"][0]["passed"]
    )
    with pytest.raises(ValueError, match="digest"):
        audit_transfer(dns_recovery, altered, allow_simulated=True)


def test_resealed_false_green_is_still_rejected(dns_recovery, simulated_transfer):
    altered = deepcopy(simulated_transfer)
    for row in altered["cases"][0]["clone_after"]:
        if row["id"] == "e2e":
            row["passed"] = True
    _reseal(altered)
    assert valid_transfer_digest(altered)
    with pytest.raises(ValueError, match="outcomes"):
        audit_transfer(dns_recovery, altered, allow_simulated=True)


def test_fake_extra_text_even_with_recomputed_digest_is_rejected(
    dns_recovery, simulated_transfer
):
    altered = deepcopy(simulated_transfer)
    altered["local_path"] = "/tmp/bravon-invalid-local-path-fixture"
    _reseal(altered)
    with pytest.raises(ValueError, match="Unknown fields"):
        audit_transfer(dns_recovery, altered, allow_simulated=True)


def test_changed_original_recovery_is_rejected(dns_recovery, simulated_transfer):
    altered = deepcopy(dns_recovery)
    altered["active_incident"]["proof"]["proof_digest"] = "0" * 64
    with pytest.raises(ValueError):
        audit_transfer(altered, simulated_transfer, allow_simulated=True)


def test_swapped_valid_antibody_fails_source_binding(dns_recovery, simulated_transfer):
    altered = deepcopy(simulated_transfer)
    altered["antibody"]["origin"]["recovery_digest"] = "f" * 64
    altered["antibody"]["policy_digest"] = digest({
        k: v for k, v in altered["antibody"].items() if k != "policy_digest"
    })
    _reseal(altered)
    with pytest.raises(ValueError, match="original recovered"):
        audit_transfer(dns_recovery, altered, allow_simulated=True)


def test_missing_control_and_repeated_check_ids_fail_closed(
    dns_recovery, simulated_transfer
):
    absent = deepcopy(simulated_transfer)
    absent["cases"].pop()
    _reseal(absent)
    with pytest.raises(ValueError, match="Both dangerous"):
        audit_transfer(dns_recovery, absent, allow_simulated=True)

    duplicate = deepcopy(simulated_transfer)
    duplicate["cases"][1]["clone_after"][0]["id"] = (
        duplicate["cases"][1]["clone_after"][1]["id"]
    )
    _reseal(duplicate)
    with pytest.raises(ValueError, match="repeated check"):
        audit_transfer(dns_recovery, duplicate, allow_simulated=True)


def test_cli_refuses_simulated_report_and_does_not_create_export(
    dns_recovery, simulated_transfer, tmp_path, capsys
):
    source_path = tmp_path / "source.json"
    source_path.write_text(json.dumps(dns_recovery), encoding="utf-8")
    transfer_path = tmp_path / "fake-report.json"
    transfer_path.write_text(json.dumps(simulated_transfer), encoding="utf-8")
    output_path = tmp_path / "not-exported.json"
    assert main([
        "--source-report", str(source_path),
        "--transfer-report", str(transfer_path),
        "--export", str(output_path),
    ]) == 2
    assert "REJECTED" in capsys.readouterr().err
    assert not output_path.exists()


def test_fake_fixture_cannot_make_a_real_origin_attestation(
    dns_recovery, simulated_transfer
):
    summary = audit_transfer(dns_recovery, simulated_transfer, allow_simulated=True)
    assert "not cryptographic" in summary["limits"]
    assert "independent runner" in summary["limits"]
    assert summary["mode"] == "SIMULATED_DOCKER_TEST"
