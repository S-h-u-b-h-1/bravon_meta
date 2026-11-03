"use strict";

/** Native Node-only regression tests for the browser evidence JSON contract.
 * No network, Docker, API calls, or private recovery reports.
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const viewer = fs.readFileSync(
  path.join(__dirname, "..", "web", "immortality.js"), "utf8"
);

function browser() {
  const nodes = new Map();
  function node(id) {
    if (!nodes.has(id)) {
      nodes.set(id, {
        hidden: false,
        textContent: "",
        addEventListener(event, handler) { this[event] = handler; },
      });
    }
    return nodes.get(id);
  }
  vm.runInNewContext(viewer, {
    document: { getElementById: node },
  }, { filename: "web/immortality.js" });
  return {
    node,
    async open(payload, name = "private-report.json") {
      const file = {
        name,
        size: 1000,
        async text() { return JSON.stringify(payload); },
      };
      await node("evidence-file").change({ target: { files: [file] } });
    },
  };
}

function transfer() {
  const records = ["dns-record", "proxy-route", "upstream-health", "e2e", "standby"];
  const checked = ids => records.map(id => ({
    id, passed: !ids.includes(id),
  }));
  return {
    schema: "bravon.immortality-transfer.v1",
    mode: "REAL_ISOLATED_DOCKER",
    status: "verified-experimental-transfer",
    antibody: {
      schema: "bravon.antibody.v1",
      family: "dns-gateway-binding",
      rule: "Candidate DNS answer must equal declared gateway",
      origin: {
        model: "hosted-muse:official-meta:muse-spark-1.3",
        action: "restore_dns",
        recovery_digest: "f".repeat(64),
      },
    },
    destination: { system: "B", slot: 150 },
    cases: [
      {
        case: "dangerous-change", policy_decision: "BLOCK",
        observed: true, expected_effect_observed: true,
        clone_before: checked([]), clone_after: checked(["dns-record", "e2e"]),
      },
      {
        case: "legitimate-control", policy_decision: "ALLOW",
        observed: true, expected_effect_observed: true,
        clone_before: checked([]), clone_after: checked([]),
      },
    ],
    active_destination_remained_healthy: true,
    cleanup_ok: true,
  };
}

test("accepts actual Python-produced real transfer shape (cases[].case)", async () => {
  const page = browser();
  await page.open(transfer(), "antibody-demo-candidate-v1.json");
  assert.equal(page.node("report-view").hidden, false);
  assert.match(page.node("reader-status").textContent, /Loaded locally:/);
  assert.match(page.node("mode").textContent, /REPORTED REAL ISOLATED DOCKER/);
  assert.equal(page.node("bad-decision").textContent, "BLOCK");
  assert.equal(page.node("good-decision").textContent, "ALLOW");
  assert.match(page.node("bad-checks").textContent, /DNS answer\s+FAIL/);
  assert.match(page.node("good-checks").textContent, /End-to-end HTTP\s+PASS/);
  assert.match(page.node("conclusion-title").textContent,
               /Experiment reports a successful isolated transfer/);
  assert.match(page.node("integrity").textContent, /does not authenticate/);
});

test("synthetic preview remains clearly labeled and does not claim live proof", () => {
  const page = browser();
  page.node("preview").click();
  assert.equal(page.node("report-view").hidden, false);
  assert.match(page.node("mode").textContent, /SYNTHETIC PREVIEW/);
  assert.equal(page.node("bad-decision").textContent, "BLOCK");
  assert.equal(page.node("good-decision").textContent, "ALLOW");
  assert.match(page.node("conclusion-title").textContent,
               /Concept illustration only/);
  assert.match(page.node("reader-status").textContent, /NOT a real model or Docker result/);
});

test("rejects incorrect case ordering instead of silently promoting", async () => {
  const page = browser();
  const report = transfer();
  report.cases.reverse();
  await page.open(report);
  assert.equal(page.node("report-view").hidden, true);
  assert.match(page.node("reader-status").textContent, /Unexpected experimental case order/);
});

test("rejects obsolete name field in real record rather than masking errors", async () => {
  const page = browser();
  const report = transfer();
  report.cases[0].name = report.cases[0].case;
  delete report.cases[0].case;
  await page.open(report);
  assert.equal(page.node("report-view").hidden, true);
  assert.match(page.node("reader-status").textContent, /Report rejected/);
});

test("rejects unrelated JSON file without exporting or uploading", async () => {
  const page = browser();
  await page.open({ hello: "world" });
  assert.equal(page.node("report-view").hidden, true);
  assert.match(page.node("reader-status").textContent, /not a Bravon Immortality transfer report/);
});


test("first visit gives a visible, explicitly synthetic explanation", () => {
  const page = browser();
  assert.equal(page.node("report-view").hidden, false);
  assert.match(page.node("mode").textContent, /GUIDED EXAMPLE.*SYNTHETIC PREVIEW/);
  assert.equal(page.node("bad-decision").textContent, "BLOCK");
  assert.equal(page.node("good-decision").textContent, "ALLOW");
  assert.match(page.node("source-model").textContent, /no model called/i);
  assert.match(page.node("bad-checks").textContent, /No Docker observations/);
  assert.match(page.node("reader-status").textContent, /NOT a real model or Docker result/);
});

test("reset after a real record restores honest synthetic state", async () => {
  const page = browser();
  await page.open(transfer());
  assert.match(page.node("mode").textContent, /REPORTED REAL/);
  page.node("clear-report").click();
  assert.match(page.node("mode").textContent, /SYNTHETIC PREVIEW/);
  assert.match(page.node("source-model").textContent, /no model called/i);
  assert.match(page.node("conclusion-title").textContent, /Concept illustration only/);
});

test("fake green controller report cannot be presented as a qualified real transfer", async () => {
  const page = browser();
  const report = transfer();
  report.cases[0].clone_after = report.cases[0].clone_after.map(c => ({
    ...c, passed: true,
  }));
  await page.open(report);
  assert.match(page.node("conclusion-title").textContent,
               /Not qualified as a complete real-world transfer/);
  assert.match(page.node("bad-check-label").textContent, /Inspect evidence/);
});

test("missing probe, invalid verdict and missing cleanup refuse green qualification", async () => {
  const page = browser();
  const report = transfer();
  report.cases[1].clone_after.pop();
  report.cleanup_ok = false;
  await page.open(report);
  assert.match(page.node("conclusion-title").textContent,
               /Not qualified as a complete real-world transfer/);
  assert.match(page.node("good-checks").textContent, /Expected five distinct/);
});

test("file over 1 MB fails closed before reading any JSON", async () => {
  const page = browser();
  await page.node("evidence-file").change({target: {files: [{
    size: 1024 * 1024 + 1,
    name: "oversized.json",
    text() { throw new Error("should not read oversized file"); },
  }]}});
  assert.equal(page.node("report-view").hidden, true);
  assert.match(page.node("reader-status").textContent, /exceeds the 1 MB/);
});
