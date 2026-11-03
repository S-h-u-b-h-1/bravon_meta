(() => {
  "use strict";
  let state = null, busy = false, pendingAction = null;
  const $ = id => document.getElementById(id);
  const hosted = !["localhost","127.0.0.1","::1"].includes(location.hostname) || new URLSearchParams(location.search).get("hosted_preview") === "1";
  if (hosted) {
    document.body.classList.add("remote-hosted");
    const heroHeading = document.querySelector(".hero h1");
    const heroDescription = document.querySelector(".hero p");
    if (heroHeading) heroHeading.textContent = "Real infrastructure, verifiable evidence.";
    if (heroDescription) heroDescription.textContent = "This public page presents the owner-authorized Docker experiment workflow and locally inspected evidence. Real container operations are restricted to isolated operator environments.";
  }
  const safe = v => String(v ?? "").replace(/[&<>"']/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));

  function toast(text, error = false) {
    const el = $("toast");
    el.textContent = text;
    el.className = "toast active" + (error ? " error" : "");
    setTimeout(() => { el.className = "toast"; }, 5000);
  }
  async function request(path, payload) {
    const options = {cache: "no-store", method: payload === undefined ? "GET" : "POST"};
    if (payload !== undefined) {
      options.headers = {"Content-Type": "application/json", "X-ProofOps-Local-Intent": "proofops-local-console"};
      options.body = JSON.stringify(payload);
    }
    let response;
    try { response = await fetch(path, options); } catch (_) { throw new Error("Cannot reach the local Bravon server"); }
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    return data;
  }
  function statusOf(id) { return (state?.checks || []).find(c => c.id === id)?.passed; }
  function markNode(id, passed) {
    const el = $(id);
    el.classList.toggle("critical", passed === false);
    el.classList.toggle("operational", passed === true);
  }
  function render() {
    const initialized = !!state?.initialized;
    const enabled = !!state?.enabled;
    const incident = state?.active_incident;
    const incidentActive = initialized && incident && incident.status !== "recovered";
    const verified = incidentActive && incident?.status === "verified" && incident?.verification?.success;
    const recovered = incident?.status === "recovered";
    const checkCount = (state?.checks || []).filter(c => c.passed).length;
    const total = (state?.checks || []).length;
    $("mode-pill").textContent = hosted ? "LOCAL DOCKER ONLY" : !enabled ? "DISABLED" : initialized ? "REAL DOCKER LAB" : "DOCKER LAB READY";
    $("service-state").textContent = !initialized ? "Offline" : state.service_status === "healthy" ? "Healthy" : "Degraded";
    $("service-state").classList.toggle("red", initialized && state.service_status !== "healthy");
    $("service-caption").textContent = initialized ? "Observed Docker environment" : "Stack not running";
    $("checks-score").textContent = initialized ? `${checkCount} / ${total}` : "—";
    $("checks-pill").textContent = initialized ? `${checkCount} / ${total}` : "— / 5";
    $("revision").textContent = initialized ? String(state.revision) : "—";
    $("recovered").textContent = String(state?.history?.length || 0);
    $("project-id").textContent = initialized ? state.project : "OFFLINE";
    $("incident-tag").textContent = incident?.status?.toUpperCase() || "NO INCIDENT";
    const banner = $("banner");
    banner.className = "banner " + (!enabled ? "warn" : initialized && state.service_status === "critical" ? "warn" : "info");
    banner.textContent = hosted ? "This website cannot run Docker containers. The real lab requires an authorized local Docker environment. For a working interactive demo, open Simulation." : !enabled ? "Real Docker controls are disabled. Restart with PROOFOPS_ENABLE_DOCKER_UI=1 ./scripts/start-local.sh, or use the safe proofops-docker CLI." :
      !initialized ? "This is a real, disposable Docker Compose environment. Starting it downloads/builds images and creates two private-only /24 test networks when verification runs." :
      `Connected to ${state.project}. Real Docker observations. Any hosted AI investigation requires explicit Terminal consent.`;
    if (hosted) {
      banner.setAttribute("role","status");
      if (!$("hosted-docker-actions")) {
        const links=document.createElement("p");
        links.id="hosted-docker-actions";
        links.className="docker-hosted-actions";
        const demo=document.createElement("a");
        demo.href="/simulation";
        demo.textContent="Try an interactive simulated failure →";
        links.appendChild(demo);
        const note=document.createElement("span");
        note.textContent=" Real Docker tests, recovery and Meta Muse remain available only in an approved local operator session.";
        links.appendChild(note);
        banner.insertAdjacentElement("afterend",links);
      }
    }
    $("start-btn").disabled = busy || !enabled || initialized;
    $("stop-btn").disabled = busy || !initialized;
    $("reset-btn").disabled = busy || !initialized;
    const qualifiedHosted = !!(incident?.diagnostic_source?.startsWith("openrouter-free:") &&
      incident?.evidence_gate?.allowed && incident?.action && incident.action !== "none");
    // A judged AI result must not be silently replaced by a local baseline.
    $("analyze-btn").disabled = busy || !incidentActive || qualifiedHosted || verified;
    $("investigate-btn").disabled = busy || !incidentActive || qualifiedHosted || verified;
    $("verify-btn").disabled = busy || !incidentActive || !incident.action || incident.action === "none" || verified;
    $("repair-btn").disabled = busy || !verified;
    document.querySelectorAll("[data-scenario]").forEach(el => { el.disabled = busy || !initialized || !!incidentActive; });
    ["step-1","step-2","step-3","step-4"].forEach((id,i) => {
      const reached = [!!incident, !!incident?.action, !!incident?.verification?.success, recovered][i];
      $(id).textContent = reached ? "COMPLETE" : "WAITING";
      $(id).className = reached ? "done" : "";
    });
    $("check-list").innerHTML = initialized ? state.checks.map(c => `
      <div class="check"><span class="check-status ${c.passed ? "good" : "bad"}">${c.passed ? "✓" : "×"}</span><div><strong>${safe(c.name)}</strong><small>${safe(c.observed)} <span>→</span> ${safe(c.expected)}</small></div><b class="${c.passed ? "good-text" : "bad-text"}">${c.passed ? "PASS" : "FAIL"}</b></div>`).join("") : "<div class='empty'>Start the Docker lab to read evidence.</div>";
    markNode("dns-node", statusOf("dns-record"));
    markNode("edge-node", statusOf("proxy-route"));
    markNode("backend-node", statusOf("upstream-health"));
    markNode("standby-node", statusOf("standby"));
    $("analysis").classList.toggle("empty", !incident?.action);
    const isHosted = (incident?.diagnostic_source || "").startsWith("openrouter-free:");
    const gate = incident?.evidence_gate;
    const analysisNote = isHosted
      ? "Evidence-qualified hosted AI decision is preserved; local re-diagnosis is locked. Sandbox verification and approval remain separate. NOT Meta Muse."
      : "Local deterministic or local-only investigator; no hosted inference through this dashboard button.";
    const modelResult = incident?.investigation
      ? `<small>RAW MODEL/AGENT PROPOSAL: ${safe(incident.raw_action)} · INDEPENDENT GATE: ${safe(gate?.allowed ? "ACCEPTED" : "BLOCKED")} · ${safe(gate?.reason)}</small>`
      : "";
    $("analysis").innerHTML = incident?.action ?
      `<div class="analysis-kicker">${safe(incident.diagnostic_source)}</div><strong>Promoted action: ${safe(incident.action)}</strong><small>${safe(analysisNote)}</small>${modelResult}
       ${incident.verification ? `<div class="verification-msg">Replica verification: <b>${incident.verification.success ? "PASSED" : "FAILED"}</b> · Digest ${safe(incident.verification.proof_digest?.slice(0, 16))}…</div>` : ""}` :
      "Inject a failure and choose Analyze to get a proposal grounded in live Docker probes.";
    const trace = incident?.investigation;
    const traceBox = $("trace-content");
    traceBox.textContent = trace ?
      trace.transcript.map((event, i) => {
        if (event.kind === "tool") return `${i + 1}. ${event.name}(${JSON.stringify(event.arguments)})\n   → ${JSON.stringify(event.evidence)}`;
        return `PROPOSAL: ${event.action}\nCITATIONS: ${event.evidence_ids.join(", ")}\nREASON: ${event.explanation}\nSOURCE: ${event.source}`;
      }).join("\n\n") :
      "Inject a fault and select Investigate with tools. The reference agent is local deterministic code, not Meta inference.";
    const proof = incident?.proof;
    $("proof-content").className = proof ? "proof-ready" : "proof-empty";
    $("proof-content").innerHTML = proof ? `<div class="proof-badges"><span>RECOVERY CONFIRMED</span><span>5 / 5 OBSERVED CHECKS</span><span>VERIFIED REPLICA</span></div><div class="proof-grid"><div><small>ALLOWLISTED ACTION</small><strong>${safe(proof.action)}</strong></div><div><small>REVISION</small><strong>${safe(proof.revision)}</strong></div><div><small>PROOF SHA-256 CHECKSUM</small><code>${safe(proof.proof_digest)}</code></div></div>` : "A proof packet is created only after an authorized repair completes and all real probes pass.";
    $("export-btn").disabled = !proof;
  }
  function confirmModal(title, body, action) {
    pendingAction = action;
    $("dialog-title").textContent = title;
    $("dialog-body").textContent = body;
    $("dialog-check").checked = false;
    $("dialog-confirm").disabled = true;
    $("confirm-dialog").showModal();
  }
  async function run(action, scenario) {
    if (busy) return;
    busy = true; render();
    try {
      if (action === "start") state = {enabled:true,initialized:true,...await request("/api/docker/start", {confirmation:"START LOCAL DOCKER LAB"})};
      if (action === "stop") { await request("/api/docker/stop", {confirmation:"STOP LOCAL DOCKER LAB"}); state = await request("/api/docker/status"); }
      if (action === "reset") state = {enabled:true,initialized:true,...await request("/api/docker/reset", {confirmation:"RESET LOCAL DOCKER LAB"})};
      if (action === "inject") state = {enabled:true,initialized:true,...await request(`/api/docker/inject/${scenario}`, {})};
      if (action === "analyze") state = {enabled:true,initialized:true,...await request("/api/docker/analyze", {})};
      if (action === "investigate") state = {enabled:true,initialized:true,...await request("/api/docker/investigate", {})};
      if (action === "verify") state = {enabled:true,initialized:true,...await request("/api/docker/verify", {})};
      if (action === "repair") state = {enabled:true,initialized:true,...await request("/api/docker/repair", {approved:true,expected_revision:state.revision,confirmation:"APPLY TO LOCAL DOCKER LAB"})};
      toast(action === "verify" ? "Sandbox checks passed. The active stack remains degraded until approval." :
            action === "repair" ? "Real repair completed; independent probes verified recovery." : `Action completed: ${action}`);
    } catch(err) { toast(err.message || "Operation failed", true); }
    busy = false; render();
  }
  $("start-btn").addEventListener("click", () => confirmModal("Start isolated Docker stack?", "Docker will download/build CoreDNS, Nginx, Alpine, and Python containers on an internal-only network.", "start"));
  $("reset-btn").addEventListener("click", () => confirmModal("Reset the Docker lab?", "This intentionally restores the disposable test DNS, proxy and primary backend to a healthy baseline.", "reset"));
  $("stop-btn").addEventListener("click", () => confirmModal("Stop and remove Docker containers?", "Only the known Bravon Compose projects and networks are stopped; evidence files remain on disk.", "stop"));
  $("analyze-btn").addEventListener("click", () => run("analyze"));
  $("investigate-btn").addEventListener("click", () => run("investigate"));
  $("verify-btn").addEventListener("click", () => run("verify"));
  $("repair-btn").addEventListener("click", () => confirmModal("Approve verified real repair?", `Repair '${state.active_incident.verification.action}' on ${state.project}, at revision ${state.revision}. Rollback will be attempted if probes fail.`, "repair"));
  document.querySelectorAll("[data-scenario]").forEach(el => el.addEventListener("click", () => confirmModal("Inject real service failure?", `Run '${el.dataset.scenario}' against the isolated Bravon Docker containers only.`, {action:"inject",scenario:el.dataset.scenario})));
  $("dialog-check").addEventListener("change", () => { $("dialog-confirm").disabled = !$("dialog-check").checked; });
  $("confirm-dialog").addEventListener("close", () => {
    if ($("confirm-dialog").returnValue === "confirm" && $("dialog-check").checked && pendingAction) {
      const action = pendingAction;
      pendingAction = null;
      if (typeof action === "string") run(action);
      else run(action.action, action.scenario);
    }
  });
  $("export-btn").addEventListener("click", () => {
    const incident = state?.active_incident;
    if (!incident?.proof) return;
    const doc = {schema:"proofops-recovery-v0.9",lab_type:"real-docker",
      note:"SHA-256 integrity checksum, not a digital signature",
      project:state.project,incident_id:incident.id,scenario:incident.scenario,
      diagnostic_source:incident.diagnostic_source || null,
      raw_action:incident.raw_action || null,
      promoted_action:incident.action || null,
      evidence_gate:incident.evidence_gate || null,
      investigation:incident.investigation || null,
      verification:incident.verification,recovery_proof:incident.proof};
    const blob = new Blob([JSON.stringify(doc,null,2)], {type:"application/json"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href=url; a.download=`bravon-${incident.id}-proof.json`; a.click();
    URL.revokeObjectURL(url);
  });
  (async () => { try { state = await request("/api/docker/status"); render(); } catch(err) { toast(err.message, true); } })();
})();
