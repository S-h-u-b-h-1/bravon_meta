from pathlib import Path

import pytest

from bravon_provenance import MemoryReplayStore, authenticate_evidence
from proofops.hackathon_worker import (
    IMAGE,
    RepairProposal,
    load_cases,
    sign_verification_report,
    verify_candidate,
)


ROOT = Path(__file__).resolve().parents[1]


def proposal(case_id: str, candidate: str) -> RepairProposal:
    case = load_cases(ROOT / "fixtures" / "hackathon")[case_id]
    return RepairProposal(
        case_id=case_id,
        target_file=case.target_file,
        replacement=(case.root / candidate).read_text(encoding="utf-8"),
        rationale="Minimal bounded repair for the observed regression.",
        evidence_ids=("source", "public-regression"),
        confidence=0.8,
    )


def test_loads_three_first_party_cases():
    cases = load_cases(ROOT / "fixtures" / "hackathon")
    assert set(cases) == {
        "software-refund-negative-quantity",
        "data-final-row-and-decimals",
        "infrastructure-healthcheck-hardening",
    }
    assert "@sha256:" in IMAGE


@pytest.mark.parametrize("target", ["../secret", "/tmp/escape", "other.py"])
def test_repair_proposal_cannot_escape_allowlisted_file(target):
    cases = load_cases(ROOT / "fixtures" / "hackathon")
    repair = proposal("software-refund-negative-quantity", "complete.py")
    repair = RepairProposal(**{**repair.__dict__, "target_file": target})
    with pytest.raises(ValueError):
        repair.validate(cases[repair.case_id])


def test_repair_proposal_has_bounded_patch_size():
    case = load_cases(ROOT / "fixtures" / "hackathon")["software-refund-negative-quantity"]
    repair = RepairProposal(case.id, case.target_file, "x" * 20_001, "bounded", ("source",), 0.5)
    with pytest.raises(ValueError):
        repair.validate(case)


@pytest.mark.parametrize(
    ("case_id", "candidate", "expected"),
    [
        ("software-refund-negative-quantity", "incomplete.py", "REJECTED_FALSE_GREEN"),
        ("software-refund-negative-quantity", "complete.py", "VERIFIED"),
        ("data-final-row-and-decimals", "incomplete.py", "REJECTED_FALSE_GREEN"),
        ("data-final-row-and-decimals", "complete.py", "VERIFIED"),
        ("infrastructure-healthcheck-hardening", "incomplete.py", "REJECTED_FALSE_GREEN"),
        ("infrastructure-healthcheck-hardening", "complete.py", "VERIFIED"),
    ],
)
def test_real_isolated_verification(case_id, candidate, expected):
    cases = load_cases(ROOT / "fixtures" / "hackathon")
    report = verify_candidate(cases[case_id], proposal(case_id, candidate))
    assert report.verdict == expected
    assert report.before_public.status == "ASSERT_FAIL"
    assert report.after_public.status == "PASS"
    assert report.after_hidden.status == ("PASS" if expected == "VERIFIED" else "ASSERT_FAIL")
    assert report.network == "none"
    assert report.image_digest.startswith("sha256:")


def test_report_signature_authenticates_once_and_binds_environment():
    cases = load_cases(ROOT / "fixtures" / "hackathon")
    report = verify_candidate(
        cases["software-refund-negative-quantity"],
        proposal("software-refund-negative-quantity", "complete.py"),
    )
    secret = b"runner-secret-32-bytes-minimum!!"
    envelope = sign_verification_report(
        report, runner_id="bravon-local-worker", key_id="demo-key", secret=secret,
    )
    store = MemoryReplayStore()
    keys = {("bravon-local-worker", "demo-key"): secret}
    observations = authenticate_evidence(
        envelope, case_id=envelope.case_id, runner_keys=keys, replay_store=store,
    )
    assert observations is not None
    assert observations[0].environment_fingerprint == report.image_digest
    assert observations[0].key == "verification_report_sha256"
    assert authenticate_evidence(
        envelope, case_id=envelope.case_id, runner_keys=keys, replay_store=store,
    ) is None
