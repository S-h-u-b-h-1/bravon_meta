(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const set = (id, value) => { $(id).textContent = String(value ?? "—"); };
  const status = message => set("reader-status", message);
  const schema = "bravon.immortality-transfer.v1";
  const checkIds = ["dns-record", "proxy-route", "upstream-health", "e2e", "standby"];
  const checkNames = {
    "dns-record": "DNS answer",
    "proxy-route": "Proxy upstream",
    "upstream-health": "Selected backend",
    "e2e": "End-to-end HTTP",
    "standby": "Standby health",
  };
  const expectedReal = [
    { case: "dangerous-change", policy_decision: "BLOCK", failed: ["dns-record", "e2e"] },
    { case: "legitimate-control", policy_decision: "ALLOW", failed: [] },
  ];

  function checkPattern(rows, failures) {
    if (!Array.isArray(rows) || rows.length !== checkIds.length) return false;
    const failuresSet = new Set(failures);
    const found = new Set();
    for (const row of rows) {
      if (!row || typeof row !== "object" || typeof row.id !== "string" ||
          !checkIds.includes(row.id) || found.has(row.id) ||
          typeof row.passed !== "boolean" || row.passed === failuresSet.has(row.id)) {
        return false;
      }
      found.add(row.id);
    }
    return found.size === checkIds.length;
  }

  function checks(caseData) {
    if (!caseData || !Array.isArray(caseData.clone_after)) {
      return "ILLUSTRATION ONLY\nNo Docker observations in this example.\nChoose your private JSON to inspect measured checks.";
    }
    const found = new Map();
    for (const item of caseData.clone_after) {
      if (!item || !checkIds.includes(item.id) || typeof item.passed !== "boolean" ||
          found.has(item.id)) {
        return "Check records are incomplete or malformed; no reliable probe result.";
      }
      found.set(item.id, item.passed);
    }
    if (found.size !== checkIds.length) {
      return "Expected five distinct Docker checks; evidence is incomplete.";
    }
    return checkIds.map(id => {
      const passed = found.get(id);
      return (passed ? "✓" : "×") + "  " +
        checkNames[id].padEnd(20, " ") + (passed ? "PASS" : "FAIL");
    }).join("\n");
  }

  function valid(report) {
    if (!report || typeof report !== "object" || report.schema !== schema) {
      throw new Error("This is not a Bravon Immortality transfer report.");
    }
    if (!report.antibody || report.antibody.schema !== "bravon.antibody.v1" ||
        !report.antibody.origin || !Array.isArray(report.cases) ||
        !report.destination || report.cases.length !== 2) {
      throw new Error("Required antibody, destination or experiment fields are missing.");
    }
    if (report.cases[0].case !== "dangerous-change" ||
        report.cases[1].case !== "legitimate-control") {
      throw new Error("Unexpected experimental case order.");
    }
    return report;
  }

  function render(payload) {
    const report = valid(payload);
    const synthetic = report.mode === "SYNTHETIC_POLICY_PREVIEW_ONLY";
    const real = report.mode === "REAL_ISOLATED_DOCKER";
    const risk = report.cases[0], control = report.cases[1];
    const riskDecision = risk.policy_decision || risk.decision || "Unknown";
    const controlDecision = control.policy_decision || control.decision || "Unknown";
    const patternGood = checkPattern(risk.clone_before, []) &&
      checkPattern(risk.clone_after, expectedReal[0].failed) &&
      checkPattern(control.clone_before, []) && checkPattern(control.clone_after, []);
    const qualified = report.status === "verified-experimental-transfer" && real &&
      report.active_destination_remained_healthy === true &&
      report.cleanup_ok === true &&
      riskDecision === "BLOCK" && controlDecision === "ALLOW" &&
      risk.observed === true && risk.expected_effect_observed === true &&
      control.observed === true && control.expected_effect_observed === true &&
      patternGood;
    $("report-view").hidden = false;
    set("mode", synthetic ? "GUIDED EXAMPLE · SYNTHETIC PREVIEW — NOT LIVE EVIDENCE" :
      real ? "REPORTED REAL ISOLATED DOCKER" : "SIMULATED DOCKER / TEST FIXTURE");
    $("mode").className = synthetic ? "mode synthetic" : "mode";
    set("verdict", synthetic ? "See how the experiment works" :
      qualified ? "Controller reports experimental transfer" :
      report.status === "verified-experimental-transfer" ? "Unqualified report — inspect details" :
      (report.status || "Unqualified"));
    set("integrity", "Browser display only · does not authenticate report origin or hashes");
    set("source-model", synthetic ? "Illustrative · no model called" :
      report.antibody.origin.model || "Unknown");
    set("source-action", synthetic ? "Example: restore_dns" :
      report.antibody.origin.action || "Unknown");
    const proof = String(report.antibody.origin.recovery_digest || "");
    set("proof-id", synthetic ? "No real proof in illustration" :
      (proof ? proof.slice(0, 18) + "…" : "Missing"));
    set("rule-text", report.antibody.rule || "Not declared");
    set("rule-name", report.antibody.family || "Not declared");
    set("destination-name", "System " + String(report.destination.system || "B") +
      (Number.isInteger(report.destination.slot) ? " · slot " + report.destination.slot : ""));
    set("active-healthy", report.active_destination_remained_healthy === true ?
      "YES (controller report)" : synthetic ? "Not tested" : "Not established");
    set("bad-decision", riskDecision);
    set("good-decision", controlDecision);
    set("bad-checks", checks(risk));
    set("good-checks", checks(control));
    set("bad-check-label", synthetic ? "Not measured" :
      (checkPattern(risk.clone_after, expectedReal[0].failed) ? "2 failed / 5" : "Inspect evidence"));
    set("good-check-label", synthetic ? "Not measured" :
      (checkPattern(control.clone_after, []) ? "5 of 5 passed" : "Inspect evidence"));
    $("conclusion").className = qualified ? "conclusion" : "conclusion caution";
    set("conclusion-title", qualified ?
      "Experiment reports a successful isolated transfer" :
      synthetic ? "Concept illustration only — Docker evidence absent" :
      "Not qualified as a complete real-world transfer");
    set("conclusion-detail", qualified ?
      "The dangerous candidate was blocked and failed in a disposable clone; the legitimate control passed. Active System B reportedly remained healthy. This is internally consistent controller evidence, not an external attestation." :
      synthetic ?
      "The BLOCK and ALLOW decisions below illustrate the policy's logic. No inference, probes, Docker experiment, or recovery is being performed in your browser." :
      "The supplied controller report did not satisfy every required evidence field or observed five-check pattern. Recheck it with Bravon's local offline auditor.");
    return { qualified, synthetic };
  }

  function syntheticReport() {
    return {
      schema, mode: "SYNTHETIC_POLICY_PREVIEW_ONLY", status: "policy-evaluated",
      antibody: {
        schema: "bravon.antibody.v1",
        family: "dns-gateway-binding",
        rule: "Candidate DNS answer must equal this system's declared gateway IP.",
        origin: {
          model: "ILLUSTRATIVE ONLY — NO MODEL CALLED", action: "restore_dns",
          recovery_digest: "SIMULATED-NOT-VERIFIED",
        },
      },
      destination: { system: "B", slot: 150 },
      cases: [
        { case: "dangerous-change", decision: "BLOCK" },
        { case: "legitimate-control", decision: "ALLOW" },
      ],
      active_destination_remained_healthy: null, cleanup_ok: null,
    };
  }
  function showExample() {
    render(syntheticReport());
    status("Guided example loaded. This is NOT a real model or Docker result.");
  }

  async function readLocal(file) {
    if (!file) return;
    if (file.size > 1024 * 1024) {
      $("report-view").hidden = true;
      status("Report rejected: file exceeds the 1 MB local viewing limit.");
      return;
    }
    try {
      const report = JSON.parse(await file.text());
      render(report);
      status("Loaded locally: " + file.name + " · no upload performed. Report authenticity is not verified by this page.");
    } catch (error) {
      $("report-view").hidden = true;
      status("Report rejected: " + String(error.message || "Invalid JSON"));
    }
  }

  $("preview").addEventListener("click", showExample);
  $("clear-report").addEventListener("click", () => {
    $("evidence-file").value = "";
    showExample();
  });
  $("choose-report").addEventListener("click", () => $("evidence-file").click());
  $("evidence-file").addEventListener("change", async event => {
    await readLocal(event.target.files?.[0]);
  });
  const zone = $("upload-zone");
  zone.addEventListener("dragover", event => {
    event.preventDefault();
    zone.className = "record-controls dragging";
  });
  zone.addEventListener("dragleave", () => { zone.className = "record-controls"; });
  zone.addEventListener("drop", event => {
    event.preventDefault();
    zone.className = "record-controls";
    readLocal(event.dataTransfer?.files?.[0]);
  });
  // A meaningful first view, clearly marked as illustrative: no local-file,
  // Docker, network, provider or backend access is performed on page load.
  showExample();
})();
