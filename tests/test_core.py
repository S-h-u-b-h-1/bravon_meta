from dataclasses import asdict

import pytest

from proofops.core import ConflictError, IncidentLab, SCENARIOS, fingerprint, proof_digest
from proofops.domain import LabConfig
from proofops.probes import check_all, is_healthy
from proofops.repairs import safe_action


@pytest.fixture
def lab():
    return IncidentLab()


def test_initial_state_is_healthy(lab):
    state = lab.snapshot()
    assert state["lab_type"] == "deterministic-simulation"
    assert state["live_infrastructure"] is False
    assert state["service_status"] == "healthy"
    assert state["metrics"]["passing_checks"] == 5


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_each_scenario_breaks_end_to_end(scenario, lab):
    incident = lab.inject(scenario)
    assert not is_healthy(check_all(lab.config))
    assert not next(c for c in incident.detected_checks if c.id == "e2e").passed
    assert incident.revision == lab.revision


@pytest.mark.parametrize("scenario,expected_action", [
    ("dns-drift", "restore_dns"),
    ("proxy-misroute", "restore_proxy"),
    ("backend-outage", "failover"),
])
def test_full_repair_cycle_with_sandbox_and_approval(scenario, expected_action, lab):
    incident = lab.inject(scenario)
    bad_state = lab.config.payload()
    lab.analyze(incident.id)
    assert incident.diagnosis.action == expected_action
    assert incident.diagnosis.source == "evidence-engine"
    lab.verify(incident.id)
    assert incident.status == "verified"
    assert incident.verification.success
    assert incident.verification.tests_passed == incident.verification.tests_total == 5
    assert lab.config.payload() == bad_state, "sandbox verification must NOT change lab"
    with pytest.raises(ConflictError):
        lab.execute(incident.id, approved=False, expected_revision=lab.revision)
    lab.execute(incident.id, approved=True, expected_revision=lab.revision)
    assert incident.status == "recovered"
    assert is_healthy(check_all(lab.config))
    assert all(c["passed"] for c in incident.recovery_proof["post_change_checks"])
    assert incident.recovery_proof["result"] == "recovered-in-simulated-lab"
    assert len(incident.events) >= 5


def test_approval_without_verification_rejected(lab):
    inc = lab.inject("dns-drift")
    with pytest.raises(ConflictError, match="verification"):
        lab.execute(inc.id, approved=True, expected_revision=lab.revision)


def test_cannot_verify_before_diagnosis(lab):
    inc = lab.inject("dns-drift")
    with pytest.raises(ConflictError, match="Diagnose first"):
        lab.verify(inc.id)


def test_cannot_inject_second_unresolved_incident(lab):
    lab.inject("dns-drift")
    with pytest.raises(ConflictError, match="Resolve current"):
        lab.inject("proxy-misroute")


def test_rejected_stale_revision(lab):
    inc = lab.inject("dns-drift")
    lab.analyze(inc.id)
    lab.verify(inc.id)
    with pytest.raises(ConflictError, match="stale"):
        lab.execute(inc.id, approved=True, expected_revision=lab.revision - 1)
    assert not is_healthy(check_all(lab.config))


def test_rejected_stale_fingerprint_if_changed_outside_workflow(lab):
    inc = lab.inject("dns-drift")
    lab.analyze(inc.id)
    lab.verify(inc.id)
    lab.config.proxy_upstream = "mystery-upstream"  # emulate configuration drift
    with pytest.raises(ConflictError, match="stale"):
        lab.execute(inc.id, approved=True, expected_revision=lab.revision)


def test_revision_change_blocks_verify(lab):
    inc = lab.inject("dns-drift")
    lab.analyze(inc.id)
    lab.revision += 1
    with pytest.raises(ConflictError, match="changed"):
        lab.verify(inc.id)


def test_reset_clears_lab_and_archives_active(lab):
    inc = lab.inject("backend-outage")
    state = lab.reset()
    assert state["service_status"] == "healthy"
    assert state["active_incident"] is None
    assert lab.incidents[inc.id].status == "abandoned"


def test_recovered_history_still_available_after_new_incident(lab):
    first = lab.inject("dns-drift")
    lab.analyze(first.id)
    lab.verify(first.id)
    lab.execute(first.id, approved=True, expected_revision=lab.revision)
    second = lab.inject("proxy-misroute")
    snap = lab.snapshot()
    assert len(snap["incidents"]) == 2
    assert snap["active_incident"]["id"] == second.id
    assert snap["metrics"]["recovered"] == 1


def test_unknown_action_refused(lab):
    with pytest.raises(ValueError, match="Unrecognized"):
        safe_action("rm -rf /", lab.config)
    assert lab.config == LabConfig()


def test_failover_without_standby_fails():
    with pytest.raises(ValueError, match="Standby is not healthy"):
        safe_action("failover", LabConfig(backend_b_running=False))


def test_checksums_stable_and_state_sensitive():
    assert fingerprint(LabConfig()) == fingerprint(LabConfig())
    assert fingerprint(LabConfig()) != fingerprint(LabConfig(dns_record="wrong"))
    assert proof_digest({"a": 1, "b": 2}) == proof_digest({"b": 2, "a": 1})


def test_model_never_changes_lab_in_diagnosis(lab):
    inc = lab.inject("dns-drift")
    original = asdict(lab.config)
    lab.analyze(inc.id)
    assert asdict(lab.config) == original
