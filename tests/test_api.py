from fastapi.testclient import TestClient
import pytest

from proofops.api import create_app
from proofops.core import IncidentLab


@pytest.fixture
def client():
    return TestClient(create_app(IncidentLab()))


def test_static_app_and_health(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Bravon" in response.text
    assert "Verification workspace" in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert "run_unsafe" not in response.text
    assert client.get("/api/health").json() == {"status": "ok", "product": "Bravon", "mode": "evidence-dashboard"}


def test_hackathon_dashboard_exposes_actual_recorded_runs(client):
    page = client.get("/")
    assert "Select technical failure" in page.text
    assert "ProofOps" not in page.text
    response = client.get("/api/hackathon/runs")
    assert response.status_code == 200
    runs = response.json()["runs"]
    assert len(runs) >= 6
    assert any(run["verdict"] == "VERIFIED" for run in runs)
    assert any(run["decision"] == "abstain" for run in runs)
    assert any(
        run["case_id"] == "infrastructure-healthcheck-hardening"
        and run["verdict"] == "REJECTED_FALSE_GREEN"
        for run in runs
    )
    assert all(run["inference"] == "ACTUAL_LOCAL_META_OPEN_WEIGHTS" for run in runs)
    detail = client.get(f"/api/hackathon/runs/{runs[0]['id']}")
    assert detail.status_code == 200
    assert detail.json()["schema"] == "bravon.meta-investigation.v1"


def test_hackathon_evidence_path_is_allowlisted(client):
    assert client.get("/api/hackathon/runs/../../.env").status_code in {404, 422}
    assert client.get("/api/hackathon/runs/not-a-run").status_code == 404


def test_public_deployment_is_read_only(monkeypatch):
    public = TestClient(create_app(IncidentLab()), base_url="https://bravon-meta.vercel.app")
    assert public.post("/api/scenarios/dns-drift/inject", json={}).status_code == 403
    assert public.post("/api/reset", json={}).status_code == 403


def test_http_full_cycle(client):
    response = client.post("/api/scenarios/proxy-misroute/inject", json={})
    assert response.status_code == 200
    state = response.json()
    assert state["service_status"] == "critical"
    incident_id = state["active_incident"]["id"]
    assert client.post(f"/api/incidents/{incident_id}/execute", json={"approved":True, "expected_revision":state["revision"]}).status_code == 409
    state = client.post(f"/api/incidents/{incident_id}/diagnose", json={"use_meta":False}).json()
    assert state["active_incident"]["diagnosis"]["action"] == "restore_proxy"
    state = client.post(f"/api/incidents/{incident_id}/verify", json={}).json()
    assert state["service_status"] == "critical", "sandbox cannot change real lab state"
    assert state["active_incident"]["verification"]["success"] is True
    state = client.post(f"/api/incidents/{incident_id}/execute", json={"approved":True, "expected_revision":state["revision"]}).json()
    assert state["service_status"] == "healthy"
    assert state["active_incident"]["status"] == "recovered"


def test_bad_requests_have_correct_status(client):
    assert client.post("/api/scenarios/no-such-scenario/inject", json={}).status_code == 404
    assert client.post("/api/incidents/nonexistent/verify", json={}).status_code == 404
    created = client.post("/api/scenarios/dns-drift/inject", json={}).json()
    assert client.post("/api/scenarios/dns-drift/inject", json={}).status_code == 409
    incident_id = created["active_incident"]["id"]
    assert client.post(f"/api/incidents/{incident_id}/diagnose", json={"use_meta":False}).status_code == 200
    assert client.post(f"/api/incidents/{incident_id}/execute", json={"approved":False, "expected_revision":created["revision"]}).status_code == 409


def test_reset_endpoint(client):
    client.post("/api/scenarios/dns-drift/inject", json={})
    state = client.post("/api/reset", json={}).json()
    assert state["service_status"] == "healthy"
    assert state["active_incident"] is None


class ControlledMetaProvider:
    def analyze(self, config, checks, permitted_action):
        evidence_ids = [check.id for check in checks if not check.passed]
        return {
            "summary": "Measured synthetic failure",
            "root_cause": "Evidence shows the fault",
            "reasoning": "Only measured evidence is considered",
            "action": permitted_action,
            "confidence": 0.9,
            "evidence_ids": evidence_ids,
        }


def test_reanalyze_open_incident_with_meta_after_local_diagnosis():
    client = TestClient(create_app(IncidentLab(provider=ControlledMetaProvider())))
    response = client.post("/api/scenarios/dns-drift/inject", json={})
    incident_id = response.json()["active_incident"]["id"]
    local = client.post(f"/api/incidents/{incident_id}/diagnose", json={"use_meta": False})
    assert local.status_code == 200
    assert local.json()["active_incident"]["diagnosis"]["source"] == "evidence-engine"
    verified = client.post(f"/api/incidents/{incident_id}/verify", json={})
    assert verified.status_code == 200
    assert verified.json()["active_incident"]["verification"]["success"] is True

    redo = client.post(f"/api/incidents/{incident_id}/diagnose", json={"use_meta": True})
    assert redo.status_code == 200
    active = redo.json()["active_incident"]
    assert active["diagnosis"]["source"] == "meta-muse"
    assert active["status"] == "diagnosed"
    assert active["verification"] is None, "Re-analysis must invalidate earlier verification"
    assert client.post(f"/api/incidents/{incident_id}/execute", json={"approved": True, "expected_revision": redo.json()["revision"]}).status_code == 409


def test_public_dashboard_cannot_spend_meta_credentials(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test-secret-only")
    client = TestClient(create_app(IncidentLab(provider=ControlledMetaProvider())),
                        base_url="https://bravon-meta.vercel.app")
    config = client.get("/api/config").json()
    assert config["provider"] == "Evidence engine only"
    assert config["meta_configured"] is False

    state = client.app.state.lab.inject("dns-drift")
    incident_id = state.id
    response = client.post(f"/api/incidents/{incident_id}/diagnose", json={"use_meta": True})
    assert response.status_code == 403
    assert response.json()["detail"] == "Public Bravon is read-only; run investigations on the local operator app"


def test_reanalyze_recovered_incident_is_refused_with_message():
    client = TestClient(create_app(IncidentLab(provider=ControlledMetaProvider())))
    state = client.post("/api/scenarios/dns-drift/inject", json={}).json()
    incident_id = state["active_incident"]["id"]
    client.post(f"/api/incidents/{incident_id}/diagnose", json={"use_meta": False})
    client.post(f"/api/incidents/{incident_id}/verify", json={})
    done = client.post(f"/api/incidents/{incident_id}/execute", json={"approved": True, "expected_revision": state["revision"]})
    assert done.status_code == 200
    conflict = client.post(f"/api/incidents/{incident_id}/diagnose", json={"use_meta": True})
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "Incident already recovered"


def test_model_trial_dashboard_is_read_only_mock_fallback(client, monkeypatch, tmp_path):
    # Isolate the test from any reports/ file generated by the developer.
    monkeypatch.setattr("proofops.api.MODEL_TRIALS_REPORT", tmp_path / "no-report.html")
    response = client.get("/model-trials")
    assert response.status_code == 200
    assert "OFFLINE MOCK" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert "Content-Security-Policy" in response.text
    assert "OPENROUTER_API_KEY" not in response.text
    assert "model-trials" in client.get("/").text
    assert "model-trials" in client.get("/docker").text


def test_model_trial_dashboard_renders_real_local_report_when_present(client, monkeypatch, tmp_path):
    generated = tmp_path / "model-trials-v081.html"
    generated.write_text("<!doctype html><html><body>LIVE SYNTHETIC REPORT</body></html>", encoding="utf-8")
    monkeypatch.setattr("proofops.api.MODEL_TRIALS_REPORT", generated)
    response = client.get("/model-trials")
    assert response.status_code == 200
    assert "LIVE SYNTHETIC REPORT" in response.text
    assert "OFFLINE MOCK" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_docker_ui_retains_hosted_provenance_on_export_and_locks_overwrite(client):
    script = client.get("/assets/docker.js").text
    html = client.get("/docker").text
    assert 'qualifiedHosted' in script
    assert 'investigation:incident.investigation || null' in script
    assert 'evidence_gate:incident.evidence_gate || null' in script
    assert 'diagnostic_source:incident.diagnostic_source || null' in script
    assert 'Reference probes (local)' in html
    assert 'V0.9.0' in html
