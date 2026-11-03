"""Headless Chromium release smoke test for Bravon's actual UI.

Runs only against a loopback FastAPI server with VERCEL=1 to enforce public
mutation restrictions. No Docker startup, paid model calls or uploads.
"""
from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CAPTURES = ROOT / "qa" / "artifacts"
CAPTURES.mkdir(parents=True, exist_ok=True)


def port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def ready(base: str) -> None:
    for _ in range(100):
        try:
            with urllib.request.urlopen(base + "/api/health", timeout=1.0) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.15)
    raise AssertionError("Local read-only test server did not start")


def assert_forbidden(url: str) -> None:
    request = urllib.request.Request(url, data=b"{}", method="POST")
    try:
        urllib.request.urlopen(request, timeout=4.0)
    except urllib.error.HTTPError as exc:
        assert exc.code == 403, (url, exc.code)
        return
    raise AssertionError("Unexpected public write permission: " + url)


def main() -> None:
    listen = port()
    base = f"http://127.0.0.1:{listen}"
    env = {**os.environ, "VERCEL": "1", "PROOFOPS_ENABLE_DOCKER_UI": "0"}
    with tempfile.TemporaryDirectory() as temp:
        with open(Path(temp) / "bravon-server.log", "wb") as logfile:
            server = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "proofops.api:app",
                 "--host", "127.0.0.1", "--port", str(listen)],
                cwd=ROOT, env=env, stdout=logfile, stderr=subprocess.STDOUT
            )
            try:
                ready(base)
                for endpoint in (
                    "/api/scenarios/dns-drift/inject", "/api/reset",
                    "/api/docker/inject/dns-drift"
                ):
                    assert_forbidden(base + endpoint)

                with sync_playwright() as playwright:
                    browser_name = os.environ.get("BRAVON_BROWSER", "chromium")
                    if browser_name not in {"chromium", "webkit"}:
                        raise ValueError("BRAVON_BROWSER must be chromium or webkit")
                    browser = getattr(playwright, browser_name).launch(headless=True)
                    errors: list[str] = []
                    desktop = browser.new_context(
                        viewport={"width": 1440, "height": 900}, reduced_motion="reduce"
                    )
                    page = desktop.new_page()
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    writes: list[str] = []
                    page.on("request", lambda request: writes.append(
                        request.method + " " + request.url
                    ) if request.method not in ("GET", "HEAD", "OPTIONS") else None)

                    home = page.goto(base + "/#tour", wait_until="domcontentloaded")
                    assert home and home.status == 200
                    expect(page.locator("#proof-journey-heading")).to_be_visible()
                    expect(page.locator("#proof-journey-record")).not_to_have_text("Record not loaded")
                    expect(page.locator("#proof-journey-content")).to_contain_text("The incident")
                    page.screenshot(path=str(CAPTURES / "desktop-proof-journey.png"), full_page=True)

                    page.locator("#proof-compare").click()
                    expect(page.locator("#proof-journey-content")).to_contain_text(
                        "The same green check can hide a different outcome"
                    )
                    expect(page.locator(".proof-compare-case")).to_have_count(2)
                    expect(page.locator(".proof-compare-table tbody tr")).to_have_count(3)
                    expect(page.locator("#proof-journey-next")).to_be_disabled()
                    page.screenshot(path=str(CAPTURES / "desktop-evidence-compare.png"), full_page=True)
                    page.locator("#proof-compare").click()
                    expect(page.locator("#proof-journey-content")).to_contain_text("The incident")
                    page.locator("#proof-choice-VERIFIED").click()
                    expect(page.locator("#proof-choice-VERIFIED")).to_have_attribute("aria-pressed","true")
                    page.locator("[data-proof-stage='3']").click()
                    expect(page.locator("#proof-journey-content")).to_contain_text("VERIFIED")
                    page.locator("[data-proof-stage='4']").click()
                    expect(page.locator("#proof-journey-content")).to_contain_text("official hosted Muse")
                    assert not writes, f"Proof Journey invoked mutation: {writes}"

                    mobile = browser.new_context(
                        viewport={"width": 390, "height": 844}, is_mobile=True,
                        device_scale_factor=1, has_touch=True, reduced_motion="reduce"
                    )
                    mpage = mobile.new_page()
                    mpage.on("pageerror", lambda error: errors.append(str(error)))
                    mpage.goto(base + "/#tour", wait_until="domcontentloaded")
                    expect(mpage.locator("#proof-journey-content")).to_contain_text("The incident")
                    # Even with reduced motion selected, an off-canvas rail must
                    # stay off-screen until a user explicitly opens it.
                    rail=mpage.locator("#sidebar").bounding_box()
                    assert rail is None or rail["x"]+rail["width"] <= 1, (
                        "Reduced-motion CSS exposed the closed sidebar: "+str(rail)
                    )
                    mpage.locator("#proof-compare").click()
                    expect(mpage.locator(".proof-compare-table")).to_be_visible()
                    mpage.screenshot(path=str(CAPTURES / "mobile-evidence-compare.png"), full_page=True)
                    width = mpage.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                    assert width <= 3, f"Mobile horizontal page overflow: {width}px"
                    mpage.goto(base + "/", wait_until="domcontentloaded")
                    mpage.get_by_role("button", name="Open navigation").click()
                    expect(mpage.locator("#sidebar")).to_have_class("rail open")
                    mpage.keyboard.press("Escape")
                    expect(mpage.locator("#sidebar")).not_to_have_class("rail open")

                    # Public-hosted behavior is emulated with ?demo=1 on a
                    # loopback server; the backend write guards remain active.
                    simulation = page.goto(base + "/simulation?demo=1", wait_until="domcontentloaded")
                    assert simulation and simulation.status == 200
                    expect(page.locator("[data-scenario='dns-drift']")).to_be_enabled()
                    page.locator("[data-scenario='dns-drift']").click()
                    expect(page.locator("#metric-status")).to_have_text("Impaired")
                    page.locator("#diagnose-btn").click()
                    expect(page.locator("#verify-btn")).to_be_enabled()
                    page.locator("#verify-btn").click()
                    expect(page.locator("#apply-btn")).to_be_enabled()
                    page.locator("#apply-btn").click()
                    page.locator("#confirm-approve").check()
                    page.locator("#confirm-apply").click()
                    expect(page.locator("#metric-status")).to_have_text("Healthy")
                    page.screenshot(path=str(CAPTURES / "desktop-simulated-recovery.png"), full_page=True)
                    mpage.goto(base + "/simulation?demo=1", wait_until="domcontentloaded")
                    expect(mpage.locator(".mobile-route-nav")).to_be_hidden()
                    expect(mpage.locator(".topology-mobile-hint")).to_be_visible()
                    mpage.screenshot(path=str(CAPTURES / "mobile-simulation.png"), full_page=True)

                    docker = page.goto(base + "/docker", wait_until="domcontentloaded")
                    assert docker and docker.status == 200
                    expect(page.locator("#start-btn")).to_be_disabled()
                    assert "Docker" in page.title()
                    expect(page.locator("#remote-choose-receipt")).to_be_visible()
                    expect(page.locator("#remote-receipt-view")).to_be_hidden()
                    import json
                    from proofops.immortality import digest
                    from proofops.remote_qualification import SCHEMA as REMOTE_SCHEMA
                    from proofops.remote_qualification import LIMITATIONS as REMOTE_LIMITS
                    from proofops.remote_qualification import CHECK_IDS as REMOTE_CHECKS
                    remote_before=[
                        {"id": name, "passed": name not in ("dns-record","e2e")}
                        for name in REMOTE_CHECKS
                    ]
                    remote_after=[{"id":name,"passed":True} for name in REMOTE_CHECKS]
                    remote_ci_fixture={
                        "schema":REMOTE_SCHEMA,
                        "execution_mode":"GH_HOSTED_DISPOSABLE_DOCKER",
                        "model_inference":"NONE_RULE_BASED_ONLY",
                        "report_status":"QUALIFIED_CONTROLLER_REPORT",
                        "run":{"repository":"S-h-u-b-h-1/bravon","run_id":"123456",
                               "attempt":"1","commit":"a"*40},
                        "requested_scenarios":["dns-drift"],
                        "results":[{
                            "scenario":"dns-drift","action":"restore_dns","result":"PASSED",
                            "before":remote_before,"sandbox_after":remote_after,
                            "recovery_after":remote_after,
                            "unapproved_repair_denied":True,"stale_revision_repair_denied":True,
                            "cleanup_to_healthy":True
                        }],
                        "five_check_invariants":list(REMOTE_CHECKS),
                        "raw_controller_digest":"b"*64,
                        "limitations":REMOTE_LIMITS
                    }
                    remote_ci_fixture["content_digest"]=digest(remote_ci_fixture)
                    page.locator("#remote-receipt-file").set_input_files({
                        "name":"synthetic-ci-minimal.json","mimeType":"application/json",
                        "buffer":json.dumps(remote_ci_fixture).encode("utf-8")
                    })
                    expect(page.locator("#remote-receipt-view")).to_be_visible()
                    expect(page.locator("#remote-report-count")).to_contain_text("1 / 1")
                    expect(page.locator("#remote-report-label")).to_contain_text("NOT an independent attestation")
                    page.screenshot(path=str(CAPTURES / "desktop-remote-receipt.png"),full_page=True)
                    remote_altered=dict(remote_ci_fixture)
                    remote_altered["run"]={**remote_ci_fixture["run"],"run_id":"987654"}
                    page.locator("#remote-receipt-file").set_input_files({
                        "name":"synthetic-altered.json","mimeType":"application/json",
                        "buffer":json.dumps(remote_altered).encode("utf-8")
                    })
                    expect(page.locator("#remote-receipt-view")).to_be_hidden()
                    expect(page.locator("#remote-receipt-status")).to_contain_text("Receipt rejected")
                    assert not writes, "Remote viewer unexpectedly issued a public mutation"
                    # In hosted read-only mode, never show unusable local repair buttons.
                    hosted_docker=page.goto(base + "/docker?hosted_preview=1",
                                             wait_until="domcontentloaded")
                    assert hosted_docker and hosted_docker.status == 200
                    expect(page.locator("#start-btn")).to_be_hidden()
                    expect(page.locator(".main-grid")).to_be_hidden()
                    expect(page.locator("#remote-choose-receipt")).to_be_visible()
                    expect(page.locator(".hero h1")).to_contain_text("Real infrastructure")
                    page.screenshot(path=str(CAPTURES / "desktop-docker-hosted-evidence.png"),
                                    full_page=True)



                    imm = page.goto(base + "/assets/immortality.html",wait_until="domcontentloaded")
                    assert imm and imm.status == 200
                    expect(page.locator("#mode")).to_contain_text("SYNTHETIC")
                    expect(page.locator("#bad-checks")).to_be_visible()
                    expect(page.locator("#good-checks")).to_be_visible()
                    page.screenshot(path=str(CAPTURES / "desktop-immortality-synthetic.png"), full_page=True)

                    # Official Muse source viewer: the browser receives no
                    # private report. Only an ephemeral synthetic CI receipt
                    # is used to exercise its local alteration checks.
                    from proofops.immortality import digest, MODEL
                    from proofops.jury_receipt import SCHEMA, EVIDENCE_LEVEL, LIMITATIONS
                    import json

                    muse=page.goto(base + "/muse",wait_until="domcontentloaded")
                    assert muse and muse.status == 200
                    expect(page.locator("#muse-evidence-mode")).to_contain_text("DOCUMENTED IN REPOSITORY")
                    expect(page.locator("#muse-model-requests")).to_have_text("7")
                    expect(page.get_by_role("link", name="Inspect the Immortality experiment")).to_be_visible()
                    page.screenshot(path=str(CAPTURES / "desktop-muse-documented.png"),full_page=True)
                    ci_receipt={
                        "schema":SCHEMA,
                        "evidence_level":EVIDENCE_LEVEL,
                        "source":{
                            "model":MODEL,"scenario":"dns-drift","proposed_action":"restore_dns",
                            "hosted_requests":7,"read_only_evidence_items":6,"cited_evidence_items":3,
                            "gate_allowed":True,"sandbox_checks_passed":5,"active_recovered":True
                        },
                        "transfer":{
                            "rule_family":"dns-gateway-binding","destination":"B",
                            "dangerous_policy":"BLOCK","dangerous_failed_checks":["dns-record","e2e"],
                            "legitimate_policy":"ALLOW","legitimate_checks_passed":5,
                            "active_preserved":True,"cleanup_recorded":True
                        },
                        "links":{
                            "source_recovery_digest":"a"*64,
                            "destination_report_digest":"b"*64
                        },
                        "limitations":LIMITATIONS
                    }
                    ci_receipt["content_digest"]=digest(ci_receipt)
                    upload={"name":"synthetic-ci-fixture.json","mimeType":"application/json",
                            "buffer":json.dumps(ci_receipt).encode("utf-8")}
                    page.locator("#muse-evidence-file").set_input_files(upload)
                    expect(page.locator("#muse-evidence-mode")).to_contain_text("NOT INDEPENDENTLY ATTESTED")
                    expect(page.locator("#muse-probes")).to_have_text("6")
                    page.screenshot(path=str(CAPTURES / "desktop-muse-local-receipt.png"),full_page=True)
                    altered=dict(ci_receipt)
                    altered["source"]={**ci_receipt["source"],"hosted_requests":9}
                    page.locator("#muse-evidence-file").set_input_files({
                        "name":"synthetic-tampered.json","mimeType":"application/json",
                        "buffer":json.dumps(altered).encode("utf-8")
                    })
                    expect(page.locator("#muse-receipt-status")).to_contain_text("Receipt rejected")
                    expect(page.locator("#muse-evidence-mode")).to_contain_text("DOCUMENTED IN REPOSITORY")
                    mpage.goto(base + "/muse",wait_until="domcontentloaded")
                    expect(mpage.locator("#muse-evidence-title")).to_be_visible()
                    mobile_width=mpage.evaluate("document.documentElement.scrollWidth-window.innerWidth")
                    assert mobile_width <= 3, f"Muse evidence overflow on mobile: {mobile_width}px"
                    mpage.screenshot(path=str(CAPTURES / "mobile-muse-documented.png"),full_page=True)
                    assert not writes, f"Muse evidence performed unexpected mutation: {writes}"

                    trials=page.goto(base + "/model-trials",wait_until="domcontentloaded")
                    assert trials and trials.status == 200
                    assert "mock" in page.content().lower()
                    expect(page.locator("main#main")).to_be_visible()
                    expect(page.locator(".model-skip")).to_have_attribute("href","#main")
                    expect(page.get_by_role("link",name="Meta Muse evidence")).to_be_visible()
                    if browser_name == "webkit":
                        page.locator(".model-skip").focus()
                    else:
                        page.keyboard.press("Tab")
                    expect(page.locator(".model-skip")).to_be_focused()
                    mpage.goto(base + "/model-trials",wait_until="domcontentloaded")
                    expect(mpage.locator("main#main")).to_be_visible()
                    assert mpage.evaluate("document.documentElement.scrollWidth-window.innerWidth") <= 3, (
                        "Archived Model Trials overflows the mobile viewport"
                    )
                    # Full-route responsive audit. A separate context for each
                    # viewport prevents session state leaking between pages.
                    # It checks browser errors, page overflow and external
                    # network requests, not automated WCAG certification.
                    audit_routes = (
                        "/", "/#tour", "/simulation?demo=1", "/docker",
                        "/muse", "/assets/immortality.html", "/model-trials"
                    )
                    audit_viewports = ((390, 844), (768, 1024), (1440, 900))
                    audit_failures = []
                    audit_results = []
                    for audit_width, audit_height in audit_viewports:
                        audit_context = browser.new_context(
                            viewport={"width": audit_width, "height": audit_height},
                            reduced_motion="reduce",
                        )
                        for audit_route in audit_routes:
                            audit_page = audit_context.new_page()
                            route_errors = []
                            external_requests = []
                            audit_page.on(
                                "pageerror",
                                lambda error, bucket=route_errors: bucket.append(str(error)),
                            )
                            audit_page.on(
                                "request",
                                lambda request, bucket=external_requests: bucket.append(request.url)
                                if not request.url.startswith(base + "/")
                                and not request.url.startswith("data:")
                                and not request.url.startswith("blob:")
                                else None,
                            )
                            response = audit_page.goto(
                                base + audit_route, wait_until="domcontentloaded"
                            )
                            audit_page.wait_for_timeout(250)
                            delta = audit_page.evaluate(
                                "document.documentElement.scrollWidth - window.innerWidth"
                            )
                            record = {
                                "route": audit_route,
                                "viewport": f"{audit_width}x{audit_height}",
                                "http_status": response.status if response else None,
                                "overflow_px": delta,
                                "page_errors": route_errors,
                                "external_requests": external_requests,
                            }
                            audit_results.append(record)
                            if not response or response.status != 200 or delta > 3:
                                audit_failures.append(str(record))
                            if route_errors or external_requests:
                                audit_failures.append(str(record))
                            audit_page.close()
                        audit_context.close()
                    (CAPTURES / "responsive-route-audit.json").write_text(
                        json.dumps(audit_results, indent=2), encoding="utf-8"
                    )
                    assert not audit_failures, (
                        "Full-route responsive audit failed: " + " | ".join(audit_failures)
                    )

                    browser.close()
                    assert not errors, "Uncaught browser errors: " + " | ".join(errors)

                print(f"Browser QA PASSED ({browser_name}): evidence tour, comparison, mobile, simulation recovery,"
                      " Docker restrictions, remote proof viewer, Muse receipts, Immortality, model trials, GET-only requests")
            finally:
                server.terminate()
                try:
                    server.wait(timeout=7)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)


if __name__ == "__main__":
    main()
