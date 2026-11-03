"""Safety tests for the opt-in single-incident CLI. Every subprocess is faked."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from proofops import muse_live_one


INCIDENT = "ab12cd34ef56"


def status(*, healthy=False, id=INCIDENT, qualified=False):
    return {
        "project": "proofops-a-fixture", "revision": 2,
        "service_status": "healthy" if healthy else "critical",
        "fingerprint": "fixture-evidence",
        "active_incident": {
            "id": id, "status": "diagnosed" if qualified else "open",
            "evidence_fingerprint": "fixture-evidence",
            "verification": None,
            "diagnostic_source": (muse_live_one.MODEL_LABEL if qualified else None),
            "evidence_gate": ({"allowed": True} if qualified else None),
        },
    }


def report():
    return {
        "service_status": "critical",
        "active_incident": {
            "id": INCIDENT,
            "diagnostic_source": muse_live_one.MODEL_LABEL,
            "raw_action": "restore_proxy", "action": "none",
            "evidence_gate": {"allowed": False},
        },
        "hosted_model_usage": {
            "requests": 7, "input_tokens": 1024, "output_tokens": 512,
        },
    }


def patch_subprocess(monkeypatch, *, state=None, second_state=None, outcome=None, exit_code=0):
    calls = []
    status_calls = 0
    if state is None:
        state = status()
    if outcome is None:
        outcome = report()

    def fake_run(argv, **kwargs):
        nonlocal status_calls
        snapshot = {**kwargs}
        if "env" in snapshot:
            snapshot["env"] = dict(snapshot["env"])
        calls.append((list(argv), snapshot))
        if "status" in argv:
            status_calls += 1
            snapshot_state = second_state if (status_calls >= 2 and second_state is not None) else state
            return SimpleNamespace(returncode=0, stdout=json.dumps(snapshot_state), stderr="")
        assert "investigate" in argv
        assert "repair" not in argv and "inject" not in argv and "reset" not in argv
        kwargs["stdout"].write(json.dumps(outcome))
        return SimpleNamespace(returncode=exit_code, stdout=None, stderr="fake error")

    monkeypatch.setattr(muse_live_one.subprocess, "run", fake_run)
    return calls


def test_operator_decline_never_contacts_model(monkeypatch, tmp_path):
    calls = patch_subprocess(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _: "NO")
    monkeypatch.setattr(
        muse_live_one, "getpass",
        lambda _: pytest.fail("Key prompt should not occur after refusal"),
    )
    out = tmp_path / "declined.json"
    assert muse_live_one.main(["--incident", INCIDENT, "--output", str(out)]) == 0
    assert len(calls) == 1 and "status" in calls[0][0]
    assert not out.exists()


@pytest.mark.parametrize("state", [
    status(healthy=True),
    status(id="other-incident"),
    status(qualified=True),
    {**status(), "fingerprint": "changed-during-evaluation"},
])
def test_preflight_refuses_stale_or_ineligible_state(monkeypatch, tmp_path, state):
    calls = patch_subprocess(monkeypatch, state=state)
    monkeypatch.setattr(
        "builtins.input",
        lambda _: pytest.fail("Consent must not be requested for an invalid incident"),
    )
    out = tmp_path / "blocked.json"
    assert muse_live_one.main(["--incident", INCIDENT, "--output", str(out)]) == 2
    assert len(calls) == 1
    assert not out.exists()


def test_preexisting_output_blocks_before_model_or_docker(monkeypatch, tmp_path):
    calls = patch_subprocess(monkeypatch)
    out = tmp_path / "already.json"
    out.write_text("preserve-this")
    assert muse_live_one.main(["--incident", INCIDENT, "--output", str(out)]) == 2
    assert not calls
    assert out.read_text() == "preserve-this"


def test_explicitly_approved_single_investigation_never_repairs(
    monkeypatch, tmp_path, capsys,
):
    calls = patch_subprocess(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _: "YES")
    secret = "synthetic-meta-secret-do-not-log"
    monkeypatch.setattr(muse_live_one, "getpass", lambda _: secret)
    out = tmp_path / "single.json"

    assert muse_live_one.main(["--incident", INCIDENT, "--output", str(out)]) == 0
    assert len(calls) == 3
    assert "status" in calls[0][0] and "status" in calls[1][0]
    cmd, options = calls[2]
    assert cmd[cmd.index("--muse-provider") + 1] == "official-meta"
    assert cmd[cmd.index("--investigator") + 1] == "hosted-muse"
    assert cmd[cmd.index("--confirm-cloud") + 1] == muse_live_one.CONSENT
    assert options["env"]["MODEL_API_KEY"] == secret  # fake subprocess snapshot only
    assert secret not in out.read_text()
    assert "repair" not in cmd and "inject" not in cmd and "reset" not in cmd
    assert out.exists()
    assert secret not in out.read_text()
    assert "Active repair: NOT PERFORMED" in capsys.readouterr().out


def test_hosted_failure_retains_report_and_never_retries(monkeypatch, tmp_path):
    calls = patch_subprocess(monkeypatch, exit_code=2)
    monkeypatch.setattr("builtins.input", lambda _: "YES")
    monkeypatch.setattr(muse_live_one, "getpass", lambda _: "synthetic-secret")
    out = tmp_path / "failure.json"
    assert muse_live_one.main(["--incident", INCIDENT, "--output", str(out)]) == 2
    assert len(calls) == 3
    assert "investigate" in calls[2][0]
    assert out.exists(), "Post-failure evidence must not be silently overwritten"


def test_incident_drift_during_key_entry_blocks_all_paid_calls(monkeypatch, tmp_path):
    changed = {**status(), "revision": 3}
    calls = patch_subprocess(monkeypatch, second_state=changed)
    monkeypatch.setattr("builtins.input", lambda _: "YES")
    monkeypatch.setattr(muse_live_one, "getpass", lambda _: "synthetic-secret")
    out = tmp_path / "stale.json"

    assert muse_live_one.main(["--incident", INCIDENT, "--output", str(out)]) == 2
    assert len(calls) == 2
    assert all("status" in argv for argv, _options in calls)
    assert not out.exists()
