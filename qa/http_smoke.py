"""Public-mode HTTP smoke check; no Docker, hosted AI, or external network.

Starts the real FastAPI app on a loopback-only ephemeral port with VERCEL=1.
Verifies every jury route, referenced same-origin assets, security headers,
and public write-denial. Designed to work where Chromium is unavailable.

This is HTTP/ASGI integration evidence, NOT rendered-browser QA or a
physical Docker/Meta Muse experiment.
"""
from __future__ import annotations

from html.parser import HTMLParser
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ROUTES = (
    "/", "/#tour", "/simulation", "/docker",
    "/muse", "/assets/immortality.html", "/model-trials",
)
SENSITIVE_WRITES = (
    "/api/scenarios/dns-drift/inject", "/api/reset",
    "/api/docker/start", "/api/docker/inject/dns-drift",
)
REQUIRED_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "cross-origin-opener-policy": "same-origin",
}


class AssetRefs(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "script":
            uri = values.get("src")
        elif tag == "link" and values.get("rel") in ("stylesheet", "icon", "preload"):
            uri = values.get("href")
        else:
            return
        if not uri or not uri.startswith("/assets/"):
            return
        address = urlsplit(uri)
        if address.query or address.fragment or ".." in address.path.split("/"):
            raise AssertionError("Unsafe or ambiguous local asset reference")
        self.references.add(address.path)


def _port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _get(base: str, path: str) -> tuple[int, dict[str, str], bytes]:
    request = Request(base + path, method="GET")
    try:
        with urlopen(request, timeout=7) as response:
            return response.status, dict(response.headers.items()), response.read(2_000_001)
    except HTTPError as exc:
        raise AssertionError(f"{path}: HTTP {exc.code}") from exc


def _status(base: str, path: str, method: str = "GET") -> int:
    # Supply a structurally valid body so denied Docker calls return 403,
    # rather than an unrelated request-model validation error (HTTP 422).
    data = b'{"confirmation":"START LOCAL DOCKER LAB"}' if method == "POST" else None
    request = Request(base + path, data=data,
                      headers={"Content-Type": "application/json"}, method=method)
    try:
        with urlopen(request, timeout=7) as response:
            return response.status
    except HTTPError as exc:
        return exc.code


def _headers(headers: dict[str, str], path: str) -> None:
    lower = {key.lower(): value for key, value in headers.items()}
    for name, expected in REQUIRED_HEADERS.items():
        if lower.get(name) != expected:
            raise AssertionError(f"{path}: unexpected {name}")
    csp = lower.get("content-security-policy", "")
    for part in ("script-src 'self'", "object-src 'none'", "frame-ancestors 'none'"):
        if part not in csp:
            raise AssertionError(f"{path}: missing CSP restriction {part}")


def run(base: str) -> dict[str, object]:
    visited: list[str] = []
    found_assets: set[str] = set()
    for route in ROUTES:
        # Fragment routes share a server resource; the browser owns '#tour'.
        path = urlsplit(route).path or "/"
        status, headers, body = _get(base, path)
        if status != 200:
            raise AssertionError(f"{route}: HTTP {status}")
        if len(body) >= 2_000_001:
            raise AssertionError(f"{route}: response too large for fixed smoke limit")
        _headers(headers, route)
        if b"<html" not in body[:500].lower() and b"<!doctype html" not in body[:500].lower():
            raise AssertionError(f"{route}: expected HTML document")
        parser = AssetRefs()
        parser.feed(body.decode("utf-8"))
        found_assets.update(parser.references)
        visited.append(route)
    if len(found_assets) < 10:
        raise AssertionError(f"Referenced asset count suspicious: {len(found_assets)}")
    for asset in sorted(found_assets):
        status, headers, body = _get(base, asset)
        if status != 200 or not body:
            raise AssertionError(f"{asset}: missing or empty asset")
        _headers(headers, asset)
    if _status(base, "/api/health") != 200:
        raise AssertionError("Application health endpoint is unavailable")
    status, _headers_used, body = _get(base, "/api/hackathon/runs")
    index = json.loads(body)
    if status != 200 or index.get("execution") != "disabled-on-public-web":
        raise AssertionError("Public evidence index mode is not read-only")
    docker_status, _, docker_body = _get(base, "/api/docker/status")
    if docker_status != 200 or json.loads(docker_body).get("enabled") is not False:
        raise AssertionError("Public Docker API must explicitly report disabled")
    for target in SENSITIVE_WRITES:
        status = _status(base, target, "POST")
        if status != 403:
            raise AssertionError(f"Public mutation guard FAILED: {target} HTTP {status}")
    return {
        "route_entries_checked": len(visited),
        "distinct_http_paths_checked": len({urlsplit(route).path or "/" for route in visited}),
        "assets_checked": len(found_assets),
        "mutation_routes_denied": len(SENSITIVE_WRITES),
        "public_docker_disabled": True,
        "test_initiated_docker_commands": 0,
        "test_initiated_model_requests": 0,
    }


def main() -> int:
    listen = _port()
    base = f"http://127.0.0.1:{listen}"
    env = dict(os.environ, VERCEL="1", PROOFOPS_ENABLE_DOCKER_UI="0")
    # The read-only smoke must never pass accidental model/provider secrets
    # into its FastAPI subprocess.
    for name in list(env):
        key = name.upper()
        if any(marker in key for marker in ("API_KEY", "_TOKEN", "_SECRET", "PASSWORD")):
            env.pop(name, None)
    with tempfile.TemporaryDirectory(prefix="bravon-http-smoke-") as tmp:
        # Never expose localhost server beyond this sandbox/process.
        with (Path(tmp) / "uvicorn.log").open("wb") as logs:
            server = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "proofops.api:app",
                 "--host", "127.0.0.1", "--port", str(listen)],
                cwd=ROOT, env=env, stdout=logs, stderr=subprocess.STDOUT,
            )
            try:
                ready = False
                for _ in range(70):
                    if server.poll() is not None:
                        raise AssertionError("Local FastAPI app exited during HTTP smoke")
                    try:
                        if _status(base, "/api/health") == 200:
                            ready = True
                            break
                    except (URLError, OSError):
                        pass
                    time.sleep(0.15)
                if not ready:
                    raise AssertionError("Local FastAPI did not become ready")
                result = run(base)
                print("HTTP SMOKE PASS: " + json.dumps(result, sort_keys=True))
                print("These checks are not a real-browser or real-Docker certification.")
                return 0
            except (AssertionError, URLError, OSError, ValueError, json.JSONDecodeError) as exc:
                print("HTTP SMOKE FAIL: " + str(exc), file=sys.stderr)
                return 1
            finally:
                server.terminate()
                try:
                    server.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
