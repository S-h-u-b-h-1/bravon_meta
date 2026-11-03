"""Bravon UI route continuity, static asset delivery and readonly contract.

These tests do not start Docker or perform incident mutation.
"""
from fastapi.testclient import TestClient

from proofops.api import create_app
from proofops.core import IncidentLab


def test_all_bravon_experiences_have_navigation_and_static_styles():
    client = TestClient(create_app(IncidentLab()))
    expectations = {
        "/": ["Immortality", "Evidence Workspace", "hackathon-polish.css", "proof-journey.js", "proof-journey.css"],
        "/simulation": ["Immortality", "Simulation", "lab-polish.css"],
        "/docker": ["Immortality", "Real Docker lab", "docker-polish.css"],
        "/muse": ["Meta Muse", "muse-evidence.css", "muse-evidence.js"],
    }
    for path, fragments in expectations.items():
        response = client.get(path)
        assert response.status_code == 200, path
        for fragment in fragments:
            assert fragment.lower() in response.text.lower(), (path, fragment)
    for name in (
        "hackathon-polish.css", "immortality.css",
        "lab-polish.css", "docker-polish.css",
        "hackathon.js", "immortality.js", "app.js", "docker.js",
        "proof-journey.js", "proof-journey.css",
        "remote-evidence.js", "remote-evidence.css",
        "muse-evidence.js", "muse-evidence.css", "muse-evidence.html",
    ):
        result = client.get(f"/assets/{name}")
        assert result.status_code == 200, name
        assert result.text.strip(), name


def test_immortality_first_visit_requires_no_local_file_or_model_request():
    client = TestClient(create_app(IncidentLab()))
    page = client.get("/assets/immortality.html")
    assert page.status_code == 200
    for fragment in (
        'id="experiment"', 'id="choose-report"',
        'id="preview"', 'id="bad-checks"', 'id="good-checks"',
        'id="reader-status"', "read-only",
    ):
        assert fragment.lower() in page.text.lower(), fragment
    js = client.get("/assets/immortality.js").text
    assert "showExample();" in js
    assert "async function readLocal(file)" in js
    assert 'document.getElementById(id)' in js


def test_jury_tour_get_only_evidence_and_verdict_contract():
    """A viewer can load published records without Docker or provider credentials."""
    client = TestClient(create_app(IncidentLab()))
    index_response = client.get("/api/hackathon/runs")
    assert index_response.status_code == 200
    result = index_response.json()
    assert result["execution"] == "disabled-on-public-web"
    runs = result["runs"]
    assert runs
    for verdict in ("VERIFIED", "REJECTED_FALSE_GREEN"):
        matching = next((run for run in runs if run["verdict"] == verdict), None)
        assert matching is not None, f"Missing jury example: {verdict}"
        report_response = client.get(f"/api/hackathon/runs/{matching['id']}")
        assert report_response.status_code == 200
        report = report_response.json()
        assert report["schema"] == "bravon.meta-investigation.v1"
        assert report["investigation"]["case_id"] == matching["case_id"]
        assert report["verification"]["verdict"] == verdict


def test_jury_public_mode_still_refuses_backend_mutation(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    client = TestClient(create_app(IncidentLab()))
    assert client.get("/api/hackathon/runs").status_code == 200
    assert client.post("/api/scenarios/dns-drift/inject").status_code == 403
    assert client.post("/api/reset").status_code == 403
    assert client.post("/api/docker/inject/dns-drift").status_code == 403
