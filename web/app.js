(() => {
  "use strict";
  let state = null;
  let config = null;
  let busy = false;
  let toastTimer;
  const publicReadOnly = !["localhost", "127.0.0.1", "::1"].includes(location.hostname);
  const $ = id => document.getElementById(id);
  const esc = input => String(input ?? "").replace(/[&<>"']/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[m]);

  function toast(message, isError = false) {
    const node = $("toast");
    node.textContent = message;
    node.className = (isError ? "show error" : "show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { node.className = ""; }, 3800);
  }

  async function api(url, payload) {
    const response = await fetch(url, {
      method: payload === undefined ? "GET" : "POST",
      headers: payload === undefined ? {} : { "Content-Type": "application/json" },
      body: payload === undefined ? undefined : JSON.stringify(payload),
      cache: "no-store",
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || `Request failed (${response.status})`);
    return result;
  }

  function timestamp(time) {
    if (!time) return "—";
    const date = new Date(time);
    return Number.isNaN(date.getTime()) ? String(time).slice(0, 19) : date.toLocaleTimeString(undefined, {hour:"2-digit", minute:"2-digit", second:"2-digit"});
  }

  function setStep(id, kind, status) {
    const node = $(id);
    node.className = "step " + (kind || "");
    $(id + "-meta").textContent = status;
  }

  function renderMetrics() {
    const healthy = state.service_status === "healthy";
    $("metric-status").textContent = healthy ? "Healthy" : "Impaired";
    $("metric-status").classList.toggle("critical", !healthy);
    $("metric-status-sub").innerHTML = `<span class="indicator ${healthy ? "indicator-success" : "indicator-fail"}"></span> ${healthy ? "All checks passing" : "One or more checks failing"}`;
    $("metric-recovered").innerHTML = `${state.metrics.recovered} <span class="metric-suffix">incidents</span>`;
    $("metric-verified").innerHTML = `${state.metrics.verified} <span class="metric-suffix">plans</span>`;
    $("metric-checks").innerHTML = `${state.metrics.passing_checks} <span class="metric-suffix">/ ${state.metrics.total_checks}</span>`;
    const badge = $("topology-status");
    badge.className = "status-chip " + (healthy ? "chip-healthy" : "chip-critical");
    badge.innerHTML = `<span></span>${healthy ? "Operational" : "Degraded"}`;
    $("topology-revision").textContent = `REV ${state.revision}`;
    $("nav-incident-count").textContent = state.metrics.incidents;
  }

  function renderTopology() {
    for (const component of state.components) {
      const el = $("node-" + component.id);
      if (!el) continue;
      const critical = component.health === "critical";
      el.classList.toggle("node-critical", critical);
      const detail = el.querySelector("[data-detail]");
      if (detail) detail.textContent = component.detail;
      const health = el.querySelector(".node-health");
      if (health) health.innerHTML = `<i></i> ${critical ? "Failing" : "Healthy"}`;
    }
  }

  function renderProbes() {
    $("probes-counter").textContent = `${state.metrics.passing_checks} / ${state.metrics.total_checks}`;
    $("probes-counter").style.color = state.metrics.passing_checks === state.metrics.total_checks ? "var(--teal)" : "var(--red)";
    $("probe-list").innerHTML = state.checks.map(check => `
      <div class="probe" title="${esc(check.detail)}">
        <span class="probe-check ${check.passed ? "" : "fail"}">${check.passed ? "✓" : "×"}</span>
        <span class="probe-details"><strong>${esc(check.name)}</strong><span>${esc(check.observed)} → ${esc(check.expected)}</span></span>
        <span class="probe-result ${check.passed ? "" : "fail"}">${check.passed ? "PASS" : "FAIL"}</span>
      </div>
    `).join("");
  }

  function renderWorkflow() {
    const incident = state.active_incident;
    const s = incident?.status;
    const diagnosed = !!incident?.diagnosis;
    const verified = !!incident?.verification?.success;
    const recovered = s === "recovered";
    const open = !!incident && !recovered && s !== "abandoned";
    const stateNames = {
      open: "FAILURE DETECTED", diagnosed: "ROOT CAUSE IDENTIFIED", verified: "READY FOR APPROVAL",
      recovered: "RECOVERED & VERIFIED", "verification-failed": "VERIFICATION FAILED", abandoned: "ABANDONED",
    };
    $("workflow-pill").textContent = s ? (stateNames[s] || s.toUpperCase()) : "WAITING FOR AN INCIDENT";
    setStep("step-detect", !incident ? "current" : "complete", !incident ? "READY" : "CAPTURED");
    setStep("step-diagnose", !incident ? "" : !diagnosed ? "current" : "complete", !incident ? "LOCKED" : !diagnosed ? "NEXT" : "COMPLETE");
    setStep("step-verify", !diagnosed ? "" : !verified ? "current" : "complete", !diagnosed ? "LOCKED" : verified ? "PASSED" : "NEXT");
    setStep("step-apply", !verified ? "" : recovered ? "complete" : "current", !verified ? "LOCKED" : recovered ? "PROVEN" : "AWAITING APPROVAL");

    // An open incident may be re-analyzed (e.g. after choosing Meta Muse).
    // Re-analysis clears any previous verification, requiring a fresh approval cycle.
    $("diagnose-btn").disabled = busy || !open;
    $("diagnose-btn").textContent = diagnosed ? "↻ Re-analyze" : "◈ Analyze";
    $("diagnose-btn").title = diagnosed
      ? "Re-analyze this unrecovered incident. Existing verification will be cleared."
      : "Analyze incident evidence";
    $("verify-btn").disabled = busy || !open || !diagnosed || verified;
    $("apply-btn").disabled = busy || !open || !verified || s !== "verified";
    document.querySelectorAll('[data-action="inject"]').forEach(el => { el.disabled = busy || !!(open); });
    $("reset-btn").disabled = busy;

    const card = $("diagnosis-card");
    if (diagnosed) {
      const d = incident.diagnosis;
      card.classList.remove("hidden");
      card.innerHTML = `
        <div class="card-kicker">ROOT CAUSE · ${esc(d.source === "meta-muse" ? "META MUSE ANALYSIS" : "DETERMINISTIC EVIDENCE ENGINE")}</div>
        <h3>${esc(d.summary)}</h3>
        <p><strong>Evidence:</strong> ${esc(d.root_cause)}</p>
        <p>${esc(d.reasoning)}</p>
        <div class="diagnosis-action">RECOMMENDED ACTION → ${esc(d.action.replaceAll("_", " ").toUpperCase())}</div>
        <p class="diagnosis-note">${esc(d.model_note)}</p>
      `;
    } else {
      card.classList.add("hidden"); card.innerHTML = "";
    }

    const proof = $("verification-card");
    if (incident?.verification) {
      const v = incident.verification;
      proof.classList.remove("hidden");
      proof.innerHTML = `
        <div class="verification-head"><span class="card-kicker">SANDBOX VERIFICATION</span><span class="verification-title" style="color:${v.success ? "var(--teal)" : "var(--red)"}">${v.success ? "✓ PASSED" : "× FAILED"}</span></div>
        <div class="proof-line"><span>Independent simulated checks</span><strong>${v.tests_passed} / ${v.tests_total}</strong></div>
        <div class="proof-line"><span>End-to-end before / after</span><strong>${v.before.find(c => c.id === "e2e")?.passed ? "PASS" : "FAIL"} → ${v.after.find(c => c.id === "e2e")?.passed ? "PASS" : "FAIL"}</strong></div>
        <div class="proof-line"><span>State revision at verification</span><strong>${v.verified_revision}</strong></div>
        <div class="proof-line"><span>Reproducibility checksum</span><code title="${esc(v.proof_digest)}">${esc(v.proof_digest.slice(0, 18))}…</code></div>
      `;
    } else { proof.classList.add("hidden"); proof.innerHTML = ""; }
  }

  function renderTimeline() {
    const incident = state.active_incident;
    if (!incident?.events.length) {
      $("event-list").innerHTML = `<div class="empty-timeline">No incident activity yet. Start with a failure scenario.</div>`;
      return;
    }
    $("event-list").innerHTML = [...incident.events].reverse().map(event => `
      <div class="event"><span class="event-marker"></span><div class="event-body"><strong>${esc(event.title)}</strong><p>${esc(event.description)}</p><div class="event-time">${esc(timestamp(event.at))}</div></div></div>
    `).join("");
  }

  function renderHistory() {
    $("history-list").innerHTML = state.incidents.length ? state.incidents.map(i => {
      const isRecovered = i.status === "recovered";
      const verification = i.verification;
      return `<div class="history-item"><span class="mono">#${esc(i.id)}</span><span>${esc(i.label)}</span><span class="${isRecovered ? "recovered" : "open"}">${esc(i.status.toUpperCase().replaceAll("-", " "))}</span><span class="${verification?.success ? "verified" : "unverified"}">${verification ? `${verification.tests_passed}/${verification.tests_total} checks` : "—"}</span></div>`;
    }).join("") : `<div class="history-empty">No incidents yet. Inject a failure to begin.</div>`;
  }

  function render() {
    if (!state) return;
    renderMetrics(); renderTopology(); renderProbes(); renderWorkflow(); renderTimeline(); renderHistory();
  }


  // Public demonstration: entirely browser-local deterministic data.
  // No writes to Vercel, real Docker, hosted inference, or shared state.
  // Explicit local QA opt-in mirrors the public browser demo without server writes.
  const demoMode = publicReadOnly || new URLSearchParams(location.search).get("demo") === "1";
  const demoBaseline = () => ({dns_record:"edge-proxy",proxy_upstream:"backend-a",backend_a_running:true,backend_b_running:true});
  let demoConfig = demoBaseline();
  let demoIncidents = [];
  let demoRevision = 1;
  const demoScenarios = {
    "dns-drift": {label:"DNS record drift",summary:"Traffic cannot find the edge proxy.",root:"The simulated DNS record points to an unknown target.",action:"restore_dns",reason:"The DNS check fails before requests reach the gateway."},
    "proxy-misroute": {label:"Gateway misroute",summary:"Traffic reaches the gateway but its upstream is invalid.",root:"The simulated gateway points to an undeclared backend.",action:"restore_proxy",reason:"The proxy route and end-to-end checks fail."},
    "backend-outage": {label:"Primary backend crash",summary:"Primary backend is down; a healthy standby remains.",root:"Backend A stopped while the proxy still targets it.",action:"failover",reason:"The simulated gateway can switch to the healthy standby."},
  };
  const demoTime = () => new Date().toISOString();
  function demoChecks(c) {
    const dns = c.dns_record === "edge-proxy";
    const route = ["backend-a","backend-b"].includes(c.proxy_upstream);
    const selected = route && (c.proxy_upstream === "backend-a" ? c.backend_a_running : c.backend_b_running);
    const check = (id,name,passed,observed,expected,detail) => ({id,name,passed,observed,expected,detail});
    return [
      check("dns-record","DNS resolution",dns,c.dns_record,"edge-proxy","Browser-only synthetic DNS record."),
      check("proxy-route","Proxy upstream",route,c.proxy_upstream,"backend-a or backend-b","Browser-only simulated gateway."),
      check("upstream-health","Selected backend",!!selected,selected?"ready":"unavailable","ready","Selected synthetic backend must be ready."),
      check("e2e","End-to-end request",!!(dns&&selected),dns&&selected?"HTTP 200":"HTTP 503 (simulated)","HTTP 200","Synthetic request path; no network traffic generated."),
      check("standby","Standby backend",c.backend_b_running,c.backend_b_running?"ready":"unavailable","ready","Synthetic standby availability."),
    ];
  }
  function demoRepair(c,action) {
    const copy={...c};
    if(action==="restore_dns") copy.dns_record="edge-proxy";
    if(action==="restore_proxy") copy.proxy_upstream="backend-a";
    if(action==="failover") copy.proxy_upstream="backend-b";
    return copy;
  }
  function demoSnapshot() {
    const checks=demoChecks(demoConfig);
    const active=demoIncidents[0] || null;
    return {
      lab_type:"browser-only-deterministic-demo",live_infrastructure:false,
      service_status:checks.every(c=>c.passed)?"healthy":"critical",
      revision:demoRevision,checks,config:{...demoConfig},
      components:[
        {id:"client",health:"healthy",detail:"GET /"},
        {id:"dns",health:demoConfig.dns_record==="edge-proxy"?"healthy":"critical",detail:demoConfig.dns_record},
        {id:"proxy",health:["backend-a","backend-b"].includes(demoConfig.proxy_upstream)?"healthy":"critical",detail:demoConfig.proxy_upstream},
        {id:"backend-a",health:demoConfig.backend_a_running?"healthy":"critical",detail:demoConfig.backend_a_running?"Online":"Stopped"},
        {id:"backend-b",health:demoConfig.backend_b_running?"healthy":"critical",detail:demoConfig.backend_b_running?"Online":"Stopped"}
      ],
      active_incident:active,incidents:demoIncidents,
      metrics:{incidents:demoIncidents.length,recovered:demoIncidents.filter(x=>x.status==="recovered").length,
        verified:demoIncidents.filter(x=>x.verification?.success).length,ai_assessments:0,
        passing_checks:checks.filter(x=>x.passed).length,total_checks:checks.length}
    };
  }
  function demoEvent(incident,title,description) { incident.events.push({at:demoTime(),title,description}); }
  function demoPerform(action,scenario) {
    let active=demoIncidents[0];
    if(action==="reset"){
      if(active && active.status!=="recovered"){active.status="abandoned";demoEvent(active,"Lab reset","Browser-only demo reset.");}
      demoConfig=demoBaseline();demoRevision++;demoIncidents=[];return demoSnapshot();
    }
    if(action==="inject"){
      const def=demoScenarios[scenario];
      if(!def)throw Error("Unknown demo scenario.");
      if(active && !["recovered","abandoned"].includes(active.status))throw Error("Reset or recover the current incident first.");
      demoConfig=demoBaseline();
      if(scenario==="dns-drift")demoConfig.dns_record="unknown-target";
      if(scenario==="proxy-misroute")demoConfig.proxy_upstream="legacy-backend";
      if(scenario==="backend-outage")demoConfig.backend_a_running=false;
      demoRevision++;
      const incident={id:"demo-"+String(demoRevision).padStart(4,"0"),scenario,label:def.label,revision:demoRevision,
        opened_at:demoTime(),status:"open",detected_checks:demoChecks(demoConfig),diagnosis:null,
        verification:null,executed_at:null,recovery_proof:null,events:[]};
      demoEvent(incident,"Failure injected","Synthetic browser-only scenario: "+def.label);
      demoIncidents.unshift(incident);return demoSnapshot();
    }
    if(!active || ["recovered","abandoned"].includes(active.status))throw Error("Introduce a simulated failure first.");
    const def=demoScenarios[active.scenario];
    if(action==="diagnose"){
      active.diagnosis={source:"evidence-engine",summary:def.summary,root_cause:def.root,
        action:def.action,reasoning:def.reason,model_note:"Deterministic browser demo only. Meta Muse was not called.",
        evidence_ids:demoChecks(demoConfig).filter(c=>!c.passed).map(c=>c.id),confidence:1};
      active.verification=null;active.status="diagnosed";
      demoEvent(active,"Root cause identified","Deterministic browser evidence engine; no Meta API call.");
    } else if(action==="verify"){
      if(!active.diagnosis)throw Error("Analyze the incident first.");
      const before=demoChecks(demoConfig),after=demoChecks(demoRepair(demoConfig,def.action));
      active.verification={action:def.action,before,after,tests_passed:after.filter(c=>c.passed).length,
        tests_total:after.length,success:after.every(c=>c.passed),verified_revision:demoRevision,
        state_fingerprint:"browser-demo-only",proof_digest:"NOT-A-CRYPTOGRAPHIC-PROOF"};
      active.status=active.verification.success?"verified":"verification-failed";
      demoEvent(active,"Sandbox demonstration checked","Browser-calculated checks; not an independent Docker verification.");
    } else if(action==="apply"){
      if(active.status!=="verified"||!active.verification?.success||active.verification.verified_revision!==demoRevision)
        throw Error("Fresh successful simulated verification required.");
      demoConfig=demoRepair(demoConfig,def.action);demoRevision++;active.status="recovered";
      active.executed_at=demoTime();
      active.recovery_proof={result:"recovered-in-browser-demo",revision:demoRevision,
        verification_digest:"NOT-A-CRYPTOGRAPHIC-PROOF"};
      demoEvent(active,"Simulated repair applied","No backend or physical infrastructure modified.");
      demoEvent(active,"Recovery confirmed","All five browser-only deterministic checks pass.");
    }
    return demoSnapshot();
  }

  async function perform(action, scenario) {
    if (demoMode) {
      if (busy) return;
      busy=true;
      try {
        state=demoPerform(action,scenario);
        toast(action==="inject"?"Synthetic failure introduced in this browser.":action==="diagnose"?"Deterministic analysis complete — no Meta API call.":action==="verify"?"Browser-only check complete.":action==="apply"?"Synthetic repair applied in this browser.":"Browser demo reset.");
      } catch(err){toast(err.message||"Demo action failed",true);}
      finally{busy=false;render();}
      return;
    }
    if (busy) return;
    busy = true; render();
    try {
      if (action === "reset") {
        state = await api("/api/reset", {});
        toast("Lab restored to a healthy baseline.");
      } else if (action === "inject") {
        state = await api(`/api/scenarios/${encodeURIComponent(scenario)}/inject`, {});
        toast("Failure injected. Observe the failing probes, then run analysis.");
      } else if (action === "diagnose") {
        const use_meta = !!$("use-meta").checked;
        const reanalyzing = !!state.active_incident.diagnosis;
        state = await api(`/api/incidents/${state.active_incident.id}/diagnose`, {use_meta});
        const diagnosis = state.active_incident.diagnosis;
        if (diagnosis.source === "meta-muse") {
          toast("Meta Muse analysis completed. " + (reanalyzing ? "Run verification again." : ""));
        } else if (use_meta) {
          toast("Meta Muse not used; see diagnosis note for fallback reason.", true);
        } else {
          toast("Root cause identified from evidence.");
        }
      } else if (action === "verify") {
        state = await api(`/api/incidents/${state.active_incident.id}/verify`, {});
        toast("Sandbox tests completed. Inspect the verification proof.");
      } else if (action === "apply") {
        state = await api(`/api/incidents/${state.active_incident.id}/execute`, {approved:true, expected_revision:state.revision});
        toast("Recovered! All final simulated probes passed.");
      }
    } catch (err) { toast(err.message || "Unexpected error", true); }
    finally { busy = false; render(); }
  }

  document.addEventListener("click", event => {
    const actionNode = event.target.closest("[data-action]");
    if (!actionNode || actionNode.disabled) return;
    const action = actionNode.dataset.action;
    if (action === "apply") {
      if (!state?.active_incident?.verification?.success) return;
      $("confirm-approve").checked = false;
      $("confirm-apply").disabled = true;
      $("approval-description").textContent = `Action: ${state.active_incident.verification.action}. Revision ${state.revision} is verified. This will modify only in-memory simulated state, then rerun the health probes.`;
      $("approve-dialog").showModal();
    } else { perform(action, actionNode.dataset.scenario); }
  });
  $("confirm-approve").addEventListener("change", () => { $("confirm-apply").disabled = !$("confirm-approve").checked; });
  $("approve-dialog").addEventListener("close", event => {
    if (event.target.returnValue === "confirm" && $("confirm-approve").checked) perform("apply");
  });
  document.querySelectorAll("[data-nav]").forEach(el => el.addEventListener("click", () => {
    document.querySelectorAll("[data-nav]").forEach(n => n.classList.remove("active"));
    el.classList.add("active");
  }));

  async function init() {
    try {
      [config, state] = await Promise.all([api("/api/config"), api("/api/state")]);
      if (config.meta_configured) {
        $("meta-toggle-wrap").classList.remove("hidden");
        $("meta-model-label").textContent = config.meta_model;
      }
      const now = new Date();
      $("demo-time").textContent = now.toLocaleDateString(undefined, {day:"2-digit",month:"short",year:"numeric"}).toUpperCase();
      if (demoMode) {
        demoConfig=demoBaseline();demoRevision=1;demoIncidents=[];
        state=demoSnapshot();
        const note=document.querySelector(".scenario-note");
        if(note)note.textContent="Interactive browser-only simulation. Nothing is sent to the server, Meta Muse, or Docker.";
        const status=document.querySelector(".topbar-chip");
        if(status)status.textContent="BROWSER DEMO · NO LIVE ACTIONS";
      }
      render();
    } catch (err) { toast("Failed to connect to Bravon backend: " + err.message, true); }
  }
  init();
})();
