"""Local WCAG audit for every public jury route; no model or Docker calls."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ROUTES = (
    "/", "/#tour", "/simulation?demo=1", "/docker", "/muse",
    "/assets/immortality.html", "/model-trials",
)
VIEWPORTS = ((390, 844), (768, 1024), (1440, 900))
TAGS = ("wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa")


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _ready(base: str) -> None:
    for _ in range(100):
        try:
            with urllib.request.urlopen(base + "/api/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.15)
    raise RuntimeError("Local read-only server did not start")


def main() -> int:
    axe_path = Path(os.environ.get("AXE_SCRIPT", ""))
    if not axe_path.is_file():
        print("AXE_SCRIPT must name a local axe.min.js file", file=sys.stderr)
        return 2
    browser_name = os.environ.get("BRAVON_BROWSER", "chromium")
    if browser_name not in {"chromium", "webkit"}:
        print("BRAVON_BROWSER must be chromium or webkit", file=sys.stderr)
        return 2
    report_path = Path(os.environ.get(
        "BRAVON_A11Y_REPORT", ROOT / "qa/artifacts/accessibility-audit.json"
    ))
    listen = _port()
    base = f"http://127.0.0.1:{listen}"
    env = {**os.environ, "VERCEL": "1", "PROOFOPS_ENABLE_DOCKER_UI": "0"}
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory() as temp:
        with (Path(temp) / "server.log").open("wb") as log:
            server = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "proofops.api:app",
                 "--host", "127.0.0.1", "--port", str(listen)],
                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                _ready(base)
                with sync_playwright() as playwright:
                    browser = getattr(playwright, browser_name).launch(headless=True)
                    for width, height in VIEWPORTS:
                        context = browser.new_context(
                            viewport={"width": width, "height": height},
                            reduced_motion="reduce",
                            bypass_csp=True,
                        )
                        for route in ROUTES:
                            page = context.new_page()
                            response = page.goto(base + route, wait_until="networkidle")
                            page.add_script_tag(path=str(axe_path))
                            audit = page.evaluate(
                                "tags => axe.run(document, {runOnly: {type: 'tag', values: tags}})",
                                list(TAGS),
                            )
                            violations = [
                                {
                                    "id": row["id"], "impact": row.get("impact"),
                                    "nodes": len(row.get("nodes", [])),
                                    "targets": [node.get("target", []) for node in row.get("nodes", [])],
                                }
                                for row in audit["violations"]
                            ]
                            results.append({
                                "route": route,
                                "viewport": f"{width}x{height}",
                                "http_status": response.status if response else None,
                                "violations": violations,
                            })
                            page.close()
                        context.close()
                    browser.close()
            finally:
                server.terminate()
                try:
                    server.wait(timeout=7)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
    report = {
        "schema": "bravon.local-accessibility-audit.v1",
        "browser": browser_name,
        "axe_tags": list(TAGS),
        "route_viewport_checks": len(results),
        "violations": sum(len(row["violations"]) for row in results),
        "results": results,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if report["violations"]:
        print(json.dumps(report, indent=2))
        return 1
    print(
        f"Accessibility audit PASSED ({browser_name}): "
        f"{len(results)} route/viewport checks, zero selected WCAG violations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
