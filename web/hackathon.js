(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  let runs = [], selected = null;

  async function get(url) {
    const response = await fetch(url, {cache: "no-store"});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
    return payload;
  }
  function toast(message, error=false) {
    const node = $("toast"); node.textContent = message; node.className = error ? "show error" : "show";
    setTimeout(() => node.className = "", 3500);
  }
  const labels = {
    overview:"Overview", tour:"Proof Journey", local:"Local incident", new:"New investigation", workspace:"Investigation workspace",
    repair:"Repair review", verification:"Verification results", report:"Evidence report", history:"Run history"
  };
  function closeNav() {
    const rail = $("sidebar"), toggle = $("nav-toggle"), backdrop = $("nav-backdrop");
    if (!rail || !toggle || !backdrop) return;
    rail.classList.remove("open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Open navigation");
    backdrop.hidden = true;
    document.body.classList.remove("nav-open");
  }
  function openNav() {
    const rail = $("sidebar"), toggle = $("nav-toggle"), backdrop = $("nav-backdrop");
    if (!rail || !toggle || !backdrop) return;
    rail.classList.add("open");
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", "Close navigation");
    backdrop.hidden = false;
    document.body.classList.add("nav-open");
  }
  function show(view) {
    if (!Object.prototype.hasOwnProperty.call(labels, view)) view = "overview";
    if (view === "local" &&
        !["localhost", "127.0.0.1", "::1"].includes(location.hostname)) {
      view = "overview";
    }
    document.querySelectorAll(".view").forEach(node => {
      node.classList.toggle("active", node.dataset.page === view);
    });
    document.querySelectorAll(".nav-item").forEach(node => {
      const active = node.dataset.view === view;
      node.classList.toggle("active", active);
      if (active) node.setAttribute("aria-current", "page");
      else node.removeAttribute("aria-current");
    });
    document.body.classList.toggle("proof-mode", view === "tour");
    $("page-title").textContent = labels[view];
    document.title = "Bravon — " + labels[view];
    history.replaceState(null, "", `#${view}`);
    document.querySelectorAll(".bravon-route-links a").forEach(link => {
      const active = link.getAttribute("href") === (view === "tour" ? "/#tour" : "/");
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    closeNav();
    window.scrollTo({top:0, behavior:matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
  }
  const cases = {
    "software-refund-negative-quantity": ["Negative refund quantity", "Software defect", "A refund function accepts negative quantities instead of rejecting invalid input."],
    "data-final-row-and-decimals": ["Dropped final revenue row", "Data-processing defect", "A revenue reducer omits the final row and risks unsafe numeric coercion."],
    "infrastructure-healthcheck-hardening": ["Unsafe service deployment", "Infrastructure configuration", "A stale health endpoint masks unsafe container and admin-listener settings."],
  };
  const titleFor = id => cases[id]?.[0] || id;
  const domainFor = id => cases[id]?.[1] || "Technical failure";
  const statusClass = value => value === "VERIFIED" ? "good" : value === "ABSTAINED" ? "neutral" : "bad";

  async function selectRun(id, destination="workspace") {
    selected = await get(`/api/hackathon/runs/${encodeURIComponent(id)}`);
    renderSelected(); show(destination);
  }


  function renderLocalDetails(state) {
    const target = $("local-detail-content");
    const incident = state.active_incident;
    if (!target) return;

    if (!incident) {
      target.textContent = "No active local incident.";
      return;
    }

    const diagnosis = incident.diagnosis;
    const verification = incident.verification;

    const beforeChecks = verification?.before ||
      incident.detected_checks || [];

    const afterChecks = new Map(
      (verification?.after || []).map(c => [c.id, c])
    );

    const rows = beforeChecks.map(before => {
      const after = afterChecks.get(before.id);

      const outcome = !after ? "NOT TESTED" :
        !before.passed && after.passed ? "RESTORED" :
        before.passed && after.passed ? "STABLE" :
        "UNRESOLVED";

      return `
        <tr>
          <td>${esc(before.name)}</td>
          <td>
            <strong class="${before.passed ? "local-pass" : "local-fail"}">
              ${before.passed ? "PASS" : "FAIL"}
            </strong>
            <small>${esc(before.observed)}</small>
          </td>
          <td>
            <strong class="${!after ? "local-pending" :
              after.passed ? "local-pass" : "local-fail"}">
              ${!after ? "NOT RUN" : after.passed ? "PASS" : "FAIL"}
            </strong>
            <small>${esc(after?.observed ?? "Not tested")}</small>
          </td>
          <td>${esc(outcome)}</td>
        </tr>`;
    }).join("");

    const checks = `
      <h3>Before vs. After</h3>
      <p>Comparison against a cloned simulation state.
         No live repair has been applied.</p>
      <div class="local-compare-scroll">
        <table class="local-compare-table">
          <thead>
            <tr>
              <th>Check</th>
              <th>Original</th>
              <th>Proposed repair</th>
              <th>Outcome</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;

    const events = (incident.events || [])
      .map(e => `
        <div style="border-top:1px solid #33434a;padding:12px 0">
          <strong>${esc(e.title)}</strong>
          <p>${esc(e.description)}</p>
          <small>${esc(e.at)}</small>
        </div>
      `).join("");

    target.innerHTML = `
      <span class="kicker">DETERMINISTIC SIMULATION</span>
      <h2>${esc(incident.label)}</h2>
      <p>Incident ID: <code>${esc(incident.id)}</code></p>
      <p>Status: ${esc(incident.status)}</p>
      <p>Revision: ${esc(incident.revision)}</p>

      <h2 style="margin-top:26px">Root cause</h2>
      <p>${esc(diagnosis?.root_cause || "Not diagnosed")}</p>
      <p>${esc(diagnosis?.reasoning || "")}</p>
      <p>Source: ${esc(diagnosis?.source || "Not available")}</p>
      <p>Evidence IDs: ${esc((diagnosis?.evidence_ids || []).join(", "))}</p>

      <h2 style="margin-top:26px">Proposed repair</h2>
      <p><code>${esc(diagnosis?.action || "No proposal")}</code></p>

      <h2 style="margin-top:26px">Simulation verification</h2>
      <p>${verification
        ? `${verification.success ? "PASSED" : "FAILED"} —
           ${verification.tests_passed}/${verification.tests_total} checks`
        : "Not performed"}</p>
      <p>Repair applied: ${incident.executed_at ? "Yes, in simulation" : "No"}</p>
      <p>Independent Docker verification: NOT PERFORMED</p>
      <p>Proof digest:
        <code>${esc(verification?.proof_digest || "Not available")}</code>
      </p>
      ${checks}

      <h2 style="margin-top:26px">Audit timeline</h2>
      ${events || "<p>No events recorded.</p>"}
    `;
  }


  async function exportLocalEvidence() {
    const local = ["localhost", "127.0.0.1", "::1"]
      .includes(location.hostname);

    if (!local) throw new Error("Local export only");

    const state = await get("/api/state");
    const incident = state.active_incident;

    if (state.lab_type !== "deterministic-simulation" || !incident) {
      throw new Error("No local simulation incident available");
    }

    const v = incident.verification;

    const report = {
      schema: "bravon.local-simulation-evidence.v1",
      exported_at: new Date().toISOString(),

      provenance: {
        environment: state.lab_type,
        diagnosis_source: incident.diagnosis?.source ?? null,
        real_docker_execution: false,
        independent_docker_verification: false,
        signed_attestation: false
      },

      incident: {
        id: incident.id,
        scenario: incident.scenario,
        label: incident.label,
        revision: incident.revision,
        opened_at: incident.opened_at,
        status: incident.status,
        repair_applied: Boolean(incident.executed_at)
      },

      initial_checks: incident.detected_checks || [],
      diagnosis: incident.diagnosis ?? null,
      proposed_repair: incident.diagnosis?.action ?? null,

      simulation_verification: v ? {
        success: v.success,
        action: v.action,
        tests_passed: v.tests_passed,
        tests_total: v.tests_total,
        before: v.before,
        after: v.after,
        verified_revision: v.verified_revision,
        state_fingerprint: v.state_fingerprint,
        proof_digest: v.proof_digest,
        proof_digest_note:
          "Simulation checksum only; not a digital signature or Docker attestation"
      } : null,

      current_simulation: {
        revision: state.revision,
        service_status: state.service_status,
        checks: state.checks || []
      },

      recovery_proof: incident.recovery_proof ?? null,
      audit_events: incident.events || []
    };

    const blob = new Blob(
      [JSON.stringify(report, null, 2) + "\n"],
      {type: "application/json"}
    );

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = "bravon-local-" +
      String(incident.id).replace(/[^a-zA-Z0-9_-]/g, "_") +
      ".json";

    document.body.appendChild(link);
    link.click();
    link.remove();

    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("Evidence download requested");
  }

  async function refreshLocalIncident() {
    const panel = $("local-incident-panel");
    const content = $("local-incident-content");

    if (!panel || !content) return;

    const localHost = ["localhost", "127.0.0.1", "::1"]
      .includes(location.hostname);

    if (!localHost) {
      panel.hidden = true;
      return;
    }

    panel.hidden = false;
    $("local-incident-nav").hidden = false;

    try {
      const state = await get("/api/state");
      const incident = state.active_incident;
      $("export-local-evidence").disabled =
        !incident || state.lab_type !== "deterministic-simulation";
      renderLocalDetails(state);

      if (state.lab_type !== "deterministic-simulation") {
        content.textContent = "Unsupported local lab type.";
        return;
      }

      if (!incident) {
        content.textContent =
          "No active simulation incident. Open the Injection Portal to create one.";
        return;
      }

      const failed = (state.checks || [])
        .filter(check => !check.passed);

      const rows = failed.map(check => `
        <article style="padding:12px 0;border-top:1px solid #32414a">
          <strong>${esc(check.name)}</strong>
          <p>Observed: <code>${esc(check.observed)}</code></p>
          <p>Expected: <code>${esc(check.expected)}</code></p>
        </article>
      `).join("");

      content.innerHTML = `
        <p><strong>${esc(incident.label)}</strong>
          · ${esc(incident.status.toUpperCase())}</p>
        <p>Incident ID: <code>${esc(incident.id)}</code>
          · Revision ${esc(state.revision)}</p>
        <p>${failed.length} failed checks out of
          ${(state.checks || []).length}</p>
        <p>Diagnosis: ${incident.diagnosis ? "Available in simulation" : "Not performed"}</p>
        <p>Simulation verification:
          ${incident.verification ? "Recorded" : "Not performed"}</p>
        <p><strong>Independent Docker verification: NOT PERFORMED</strong></p>
        <div>${rows || "No failed checks currently reported."}</div>
        <p><button class="secondary" data-local-open>View incident details →</button></p><p><a href="/simulation">Open Injection Portal</a></p>
      `;
    } catch (error) {
      content.textContent = "Local incident unavailable: " + error.message;
    }
  }

  function renderOverview() {
    $("metric-runs").textContent = runs.length;
    $("metric-verified").textContent = runs.filter(run => run.verdict === "VERIFIED").length;
    $("metric-abstained").textContent = runs.filter(run => run.decision === "abstain").length;
    $("metric-cost").textContent = `$${runs.reduce((sum, run) => sum + run.cost_usd, 0).toFixed(2)}`;
    const latest = runs[0];
    $("latest-card").className = latest ? "latest" : "empty";
    $("latest-card").innerHTML = latest ? `<div><span>${esc(domainFor(latest.case_id))}</span><strong>${esc(titleFor(latest.case_id))}</strong><small>${esc(latest.model)} · ${latest.input_tokens + latest.output_tokens} tokens · $${latest.cost_usd.toFixed(2)}</small></div><button class="secondary" data-run="${esc(latest.id)}">Inspect run →</button>` : "No recorded runs available.";
  }
  function renderCases() {
    const ids = [...new Set(runs.map(run => run.case_id))];
    $("case-grid").innerHTML = ids.map((id, index) => {
      const matching = runs.filter(run => run.case_id === id);
      const verified = matching.find(run => run.verdict === "VERIFIED") || matching[0];
      return `<article class="case-card"><span class="case-index">0${index+1}</span><div class="case-domain">${esc(domainFor(id))}</div><h2>${esc(titleFor(id))}</h2><p>${esc(cases[id]?.[2] || "Recorded bounded technical investigation.")}</p><div class="case-meta"><span>${matching.length} recorded runs</span><span>${matching.some(run=>run.verdict==="VERIFIED") ? "Verified repair available" : "No verified repair"}</span></div><button class="primary" data-run="${esc(verified.id)}">Open recorded investigation →</button></article>`;
    }).join("");
  }
  function renderHistory() {
    const query = String($("run-search")?.value || "").trim().toLowerCase();
    const verdict = $("verdict-filter")?.value || "all";
    const filtered = runs.filter(run => {
      const text = [run.id, run.case_id, titleFor(run.case_id),
        domainFor(run.case_id), run.model, run.verdict, run.decision].join(" ").toLowerCase();
      return (verdict === "all" || run.verdict === verdict) && text.includes(query);
    });
    $("history-count").textContent = filtered.length + " of " + runs.length + " recorded runs";
    $("history-list").innerHTML = filtered.length ? filtered.map(run =>
      `<button class="history-row" data-run="${esc(run.id)}"><span><strong>${esc(run.id.replace("local-meta-", ""))}</strong><small>${new Date(run.generated_at).toLocaleString()}</small></span><span>${esc(domainFor(run.case_id))}</span><span>${esc(run.decision.toUpperCase())}</span><span class="${statusClass(run.verdict)}">${esc(run.verdict.replaceAll("_", " "))}</span><span>${esc(run.model)}</span></button>`
    ).join("") : '<div class="history-empty">No recorded runs match your filters. Try another case or verdict.</div>';
  }
  function renderSelected() {
    if (!selected) return;
    const inv = selected.investigation, verification = selected.verification, proposal = inv.proposal;
    $("workspace-subtitle").textContent = `${domainFor(inv.case_id)} · recorded ${new Date(selected.generated_at).toLocaleString()}`;
    $("request-count").textContent = `${inv.requests} model requests`;
    $("model-label").textContent = inv.model;
    $("tool-trace").className = "timeline";
    $("tool-trace").innerHTML = inv.transcript.map((item, index) => item.kind === "tool" ? `<div class="trace-item"><span>${String(index+1).padStart(2,"0")}</span><div><strong>${esc(item.name.replaceAll("_"," "))}</strong><small>Returned evidence ID: ${esc(item.evidence_id)}</small></div><b>READ ONLY</b></div>` : `<div class="trace-item final"><span>${String(index+1).padStart(2,"0")}</span><div><strong>${esc(item.decision)} repair</strong><small>Cited: ${esc(item.evidence_ids.join(", "))}</small></div><b>${Math.round(item.confidence*100)}%</b></div>`).join("");
    $("hypothesis").className = "assessment";
    $("hypothesis").innerHTML = `<span>ROOT CAUSE</span><h3>${esc(inv.root_cause)}</h3><span>UNCERTAINTY</span><p>${esc(inv.uncertainty)}</p><div class="usage"><span>${inv.input_tokens} input tokens</span><span>${inv.output_tokens} output tokens</span><span>$${inv.cost_usd.toFixed(2)} cost</span></div>`;
    $("repair-file").textContent = proposal ? proposal.target_file : "Model abstained";
    $("decision-badge").textContent = proposal ? "PROPOSED" : "NO PATCH";
    $("decision-badge").className = `badge ${proposal ? "amber" : "neutral"}`;
    $("repair-code").textContent = proposal ? proposal.replacement : "No code was proposed. The unsuccessful investigation is retained as evidence.";
    $("safety-list").innerHTML = [
      ["Single allowlisted file", proposal ? proposal.target_file : "No file mutation"],
      ["Dependency installation", "Forbidden"], ["System commands", "Forbidden"],
      ["External requests", "Forbidden"], ["Model access to hidden tests", "None"]
    ].map(([label,value]) => `<div><span>✓</span><p><strong>${esc(label)}</strong><small>${esc(value)}</small></p></div>`).join("");
    renderVerification(verification);
    renderReport(selected);
  }
  function renderVerification(v) {
    const summary = $("verification-summary");
    const grid = $("test-grid");

    if (!v) {
      summary.className = "verdict-card neutral";
      summary.innerHTML = `<span>ABSTAINED</span>
        <strong>No patch entered verification.</strong>
        <p>The model's unsuccessful investigation is preserved; no repair is claimed.</p>`;
      grid.innerHTML = "";
      return;
    }

    const checks = [
      {
        name: "01 — Original defect reproduction",
        result: v.before_public,
        passes: v.before_public?.status === "ASSERT_FAIL",
        expected: "Original regression must fail with an assertion",
        goodLabel: "DEFECT REPRODUCED",
        badLabel: "NOT REPRODUCED"
      },
      {
        name: "02 — Patched regression",
        result: v.after_public,
        passes: v.after_public?.status === "PASS",
        expected: "Original regression must pass after the repair",
        goodLabel: "REGRESSION PASSED",
        badLabel: "REGRESSION FAILED"
      },
      {
        name: "03 — Independent behavior",
        result: v.after_hidden,
        passes: v.after_hidden?.status === "PASS",
        expected: "Independent behavioral checks must pass",
        goodLabel: "BEHAVIOR VERIFIED",
        badLabel: "BEHAVIOR FAILED"
      }
    ];

    const passedCount = checks.filter(check => check.passes).length;
    const verified = v.verdict === "VERIFIED";
    const falseGreen = v.verdict === "REJECTED_FALSE_GREEN";
    const reason = verified
      ? "The recorded repair passed all required verification stages."
      : falseGreen && checks[1].passes && !checks[2].passes
        ? "False-green repair: the visible regression passes, but independent behavioral tests fail."
        : "The repair was not accepted by the independent verifier.";

    summary.className = `verdict-card ${verified ? "good" : "bad"}`;
    summary.innerHTML = `<span>${esc(String(v.verdict).replaceAll("_", " "))}</span>
      <strong>${esc(reason)}</strong>
      <p>${passedCount} of ${checks.length} stages met their expected outcomes. Model confidence does not determine acceptance.</p>
      <p>Recorded execution · Network ${esc(v.network ?? "unknown")} · Image ${esc(String(v.image_digest ?? "unknown").slice(0, 24))} · ${esc(v.duration_ms ?? "unknown")} ms</p>`;

    grid.innerHTML = checks.map(check => {
      const result = check.result;
      const rawStatus = result?.status ?? "MISSING";
      return `<article>
        <div><span>${esc(check.name)}</span><b class="${check.passes ? "good" : "bad"}">${esc(check.passes ? check.goodLabel : check.badLabel)}</b></div>
        <strong>${esc(result?.test_file ?? "No test recorded")}</strong>
        <small>${esc(check.expected)} · Raw status: ${esc(rawStatus)} · ${esc(result?.duration_ms ?? "unknown")} ms · Exit: ${esc(result?.exit_code ?? "timeout/unknown")}</small>
        <pre>${esc(result?.output || "No output recorded")}</pre>
      </article>`;
    }).join("");
  }
  function renderReport(payload) {
    const inv=payload.investigation, v=payload.verification, env=payload.evidence_envelope;
    $("export-report").disabled=false;
    $("evidence-report").className="report-grid";
    $("evidence-report").innerHTML = `<article><span>RUN IDENTITY</span><dl><dt>Case</dt><dd>${esc(inv.case_id)}</dd><dt>Inference</dt><dd>${esc(payload.inference)}</dd><dt>Model</dt><dd>${esc(inv.model)}</dd><dt>Generated</dt><dd>${esc(payload.generated_at)}</dd></dl></article><article><span>EXECUTION</span><dl><dt>Verdict</dt><dd>${esc(v?.verdict || "ABSTAINED")}</dd><dt>Duration</dt><dd>${v ? v.duration_ms+" ms" : "Not run"}</dd><dt>Image</dt><dd class="mono">${esc(v?.image_digest || "—")}</dd><dt>Network</dt><dd>${esc(v?.network || "—")}</dd></dl></article><article class="wide"><span>AUTHENTICATED EVIDENCE</span><dl><dt>Runner</dt><dd>${esc(env?.runner_id || "No verification envelope")}</dd><dt>Key ID</dt><dd>${esc(env?.key_id || "—")}</dd><dt>Signature</dt><dd class="mono">${esc(env?.signature || "—")}</dd></dl><p class="fine-print">HMAC detects tampering by parties without the private runner key. It is not public-key attestation.</p></article>`;
  }
  function exportReport() {
    if (!selected) return; const blob=new Blob([JSON.stringify(selected,null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob), a=document.createElement("a"); a.href=url; a.download=`bravon-${selected.investigation.case_id}.json`; a.click(); URL.revokeObjectURL(url);
  }
  document.addEventListener("click", event => {
    if (event.target.closest("[data-local-open]")) {
      show("local");
      return;
    }
    const guided=event.target.closest("[data-demo-verdict]");
    if(guided){
      show("tour");
      window.BravonProofJourney.open(guided.dataset.demoVerdict);
      return;
    }
    const nav=event.target.closest("[data-view]"); if(nav){event.preventDefault();show(nav.dataset.view);if(nav.dataset.view==="tour")window.BravonProofJourney.open();return;}
    const go=event.target.closest("[data-go]"); if(go){show(go.dataset.go);if(go.dataset.go==="tour")window.BravonProofJourney.open();return;}
    const run=event.target.closest("[data-run]"); if(run){selectRun(run.dataset.run).catch(err=>toast(err.message,true));}
  });
  $("refresh-local-incident").addEventListener(
    "click", refreshLocalIncident
  );
  refreshLocalIncident();

  $("export-local-evidence").addEventListener("click", () => {
    exportLocalEvidence().catch(error => toast(error.message, true));
  });
  $("export-report").addEventListener("click", exportReport);
  $("run-search").addEventListener("input", renderHistory);
  $("verdict-filter").addEventListener("change", renderHistory);
  $("nav-toggle").addEventListener("click", () =>
    $("sidebar").classList.contains("open") ? closeNav() : openNav());
  $("nav-close").addEventListener("click", () => { closeNav(); $("nav-toggle").focus(); });
  $("nav-backdrop").addEventListener("click", closeNav);
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && $("sidebar").classList.contains("open")) {
      closeNav();
      $("nav-toggle").focus();
    }
  });
  window.addEventListener("resize", () => {
    if (window.innerWidth > 820) closeNav();
  });
  (async()=>{
    try {
      const response = await get("/api/hackathon/runs");
      if (!Array.isArray(response.runs)) throw new Error("Unexpected evidence index");
      runs = response.runs;
      renderOverview();
      renderCases();
      renderHistory();
      const start = location.hash.slice(1) in labels ? location.hash.slice(1) : "overview";
      show(start);
      if (start === "tour") window.BravonProofJourney.open();
      if (runs[0]) {
        try {
          selected = await get("/api/hackathon/runs/" + encodeURIComponent(runs[0].id));
          renderSelected();
        } catch (error) {
          toast("Latest investigation details unavailable: " + error.message, true);
        }
      }
    } catch (error) {
      toast("Recorded evidence unavailable: " + error.message, true);
      show("overview");
      $("latest-card").textContent = "Could not load recorded evidence. Refresh to retry.";
      $("case-grid").textContent = "Recorded case index is unavailable.";
      $("history-list").textContent = "Recorded run history is unavailable.";
    }
  })();
})();
