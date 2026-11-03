"""Negative HTTP-security regressions that do not require a live server."""
from __future__ import annotations

import json

import pytest

from qa import http_smoke


HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'",
}


def test_asset_parser_collects_only_same_origin_dependencies():
    parser = http_smoke.AssetRefs()
    parser.feed("""
        <link rel="stylesheet" href="/assets/styles.css">
        <script src="/assets/app.js"></script>
        <link rel="icon" href="/assets/icon.svg">
        <script src="https://example.invalid/foreign.js"></script>
        <a href="/assets/not-a-dependency.html">Link</a>
    """)
    assert parser.references == {
        "/assets/styles.css", "/assets/app.js", "/assets/icon.svg"
    }


def test_asset_parser_fails_closed_for_ambiguous_traversal():
    parser = http_smoke.AssetRefs()
    with pytest.raises(AssertionError, match="Unsafe or ambiguous"):
        parser.feed('<script src="/assets/../secret.js"></script>')


def test_security_headers_must_include_csp_and_clickjacking_guard():
    http_smoke._headers(HEADERS, "/muse")
    bad = {**HEADERS, "Content-Security-Policy": "default-src 'self'"}
    with pytest.raises(AssertionError, match="missing CSP restriction"):
        http_smoke._headers(bad, "/muse")


def fake_public_server(monkeypatch, *, docker_enabled=False, grant_write=False):
    # Eleven fixture script references satisfy the fixed asset-count minimum.
    html = ("<html><head>" + "".join(
        f'<script src="/assets/fixture-{i}.js"></script>' for i in range(11)
    ) + "</head><body>Fixture document</body></html>").encode()

    def get(_base, path):
        if path == "/api/hackathon/runs":
            return 200, HEADERS, json.dumps(
                {"execution": "disabled-on-public-web", "runs": []}
            ).encode()
        if path == "/api/docker/status":
            return 200, HEADERS, json.dumps(
                {"enabled": docker_enabled, "initialized": False}
            ).encode()
        if path.startswith("/assets/") and path.endswith(".js"):
            return 200, HEADERS, b"// known fixture"
        return 200, HEADERS, html

    def status(_base, _path, method="GET"):
        return 200 if method == "GET" or grant_write else 403

    monkeypatch.setattr(http_smoke, "_get", get)
    monkeypatch.setattr(http_smoke, "_status", status)


def test_public_http_smoke_fails_if_docker_becomes_enabled(monkeypatch):
    fake_public_server(monkeypatch, docker_enabled=True)
    with pytest.raises(AssertionError, match="Public Docker API must explicitly report disabled"):
        http_smoke.run("http://127.0.0.1:0")


def test_public_http_smoke_rejects_any_unexpected_mutation_success(monkeypatch):
    fake_public_server(monkeypatch, grant_write=True)
    with pytest.raises(AssertionError, match="Public mutation guard FAILED"):
        http_smoke.run("http://127.0.0.1:0")


def test_public_http_smoke_accepts_structurally_read_only_fixture(monkeypatch):
    fake_public_server(monkeypatch)
    result = http_smoke.run("http://127.0.0.1:0")
    assert result["route_entries_checked"] == 7
    assert result["distinct_http_paths_checked"] == 6
    assert result["assets_checked"] == 11
    assert result["mutation_routes_denied"] == 4
    assert result["public_docker_disabled"] is True
