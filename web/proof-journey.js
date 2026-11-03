(() => {
  "use strict";

  // Read-only product tour: every claim is derived from a saved, published run.
  // This module never invokes Docker, a model, or a mutation API.
  const $ = id => document.getElementById(id);
  const outcomes = ["REJECTED_FALSE_GREEN", "VERIFIED"];
  const steps = ["Incident", "Investigation", "Proposed repair", "Independent checks", "Scope & next step"];
  const knownCases = {
    "software-refund-negative-quantity": ["Negative refund quantity", "Software defect", "A refund function accepts negative quantities instead of rejecting them."],
    "data-final-row-and-decimals": ["Dropped final revenue row", "Data processing", "A revenue reducer omits the final row and risks unsafe numeric coercion."],
    "infrastructure-healthcheck-hardening": ["Unsafe service deployment", "Infrastructure", "A stale health endpoint masks an unsafe service configuration."]
  };
  let summaries = null;
  let current = null;
  let currentSummary = null;
  let chosen = outcomes[0];
  let step = 0;
  let generation = 0;
  let comparing = false;
  let comparison = null;

  function node(tag, className, value) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (value !== undefined) element.textContent = String(value);
    return element;
  }
  function add(parent, tag, className, value) {
    const child = node(tag, className, value);
    parent.appendChild(child);
    return child;
  }
  function heading(parent, eyebrow, title, description) {
    add(parent, "p", "proof-eyebrow", eyebrow);
    add(parent, "h2", "proof-title", title);
    if (description) add(parent, "p", "proof-description", description);
  }
  function fact(parent, label, value) {
    const row = add(parent, "div", "proof-fact");
    add(row, "span", "proof-fact-label", label);
    add(row, "strong", "proof-fact-value", value == null ? "Not recorded" : value);
  }
  function status(parent, title, expected, observed) {
    const passed = observed === expected;
    const row = add(parent, "div", "proof-check");
    add(row, "span", "proof-check-mark " + (passed ? "passed" : "failed"), passed ? "✓" : "×");
    const content = add(row, "div", "proof-check-text");
    add(content, "strong", "", title);
    add(content, "small", "", "Expected: " + expected + " · Recorded: " + (observed ?? "Not recorded"));
    add(row, "span", "proof-check-state", passed ? "Met" : "Not met");
    return passed;
  }
  function resetState() {
    current = null;
    currentSummary = null;
    step = 0;
    comparing = false;
    comparison = null;
  }
  function info(message) {
    const root = $("proof-journey-content");
    if (!root) return;
    root.replaceChildren();
    const area = add(root, "div", "proof-empty");
    add(area, "p", "", message);
  }
  async function readJSON(url) {
    const response = await fetch(url, {method:"GET", cache:"no-store"});
    if (!response.ok) throw new Error("Evidence service returned HTTP " + response.status);
    return response.json();
  }
  function renderControls() {
    for (const result of outcomes) {
      const button = $("proof-choice-" + result);
      if (!button) continue;
      const selected = result === chosen && !comparing;
      button.setAttribute("aria-pressed", String(selected));
      button.classList.toggle("selected", selected);
    }
    for (const button of document.querySelectorAll("[data-proof-stage]")) {
      const i = Number(button.dataset.proofStage);
      button.disabled = !current || comparing;
      button.classList.toggle("selected", i === step);
      if (i === step) button.setAttribute("aria-current", "step");
      else button.removeAttribute("aria-current");
    }
    const compareButton = $("proof-compare");
    compareButton.setAttribute("aria-pressed", String(comparing));
    compareButton.textContent = comparing ? "Back to single case" : "Compare the evidence";
    $("proof-journey-back").disabled = !current || comparing || step === 0;
    $("proof-journey-next").disabled = !current || comparing || step === steps.length - 1;
    $("proof-journey-back").hidden = comparing;
    $("proof-journey-next").hidden = comparing;
    $("proof-journey-progress").textContent = comparing ? "Side-by-side evidence" : "Step " + (step+1) + " of " + steps.length;
    $("proof-journey-record").textContent = comparing ? "Two separately recorded cases · read-only" : currentSummary
      ? currentSummary.id + " · " + currentSummary.model : "Record not loaded";
  }
  function render() {
    renderControls();
    if (comparing && comparison) {renderComparison();return;}
    if (!current) return;
    const root = $("proof-journey-content");
    root.replaceChildren();
    const inv = current.investigation;
    const v = current.verification;
    const caseInfo = knownCases[inv.case_id] || [inv.case_id, "Technical failure", "Recorded first-party technical fixture."];
    const result = v?.verdict || "ABSTAINED";

    if (step === 0) {
      heading(root, "01 · The incident", caseInfo[0], caseInfo[2]);
      const facts = add(root, "div", "proof-facts");
      fact(facts, "Domain", caseInfo[1]);
      fact(facts, "Execution", "Recorded local model run — not a live request");
      fact(facts, "Recorded at", current.generated_at || "Not recorded");
      fact(facts, "Case identifier", inv.case_id);
      add(root, "p", "proof-context", "We begin with the original defect and the known fixture. The investigator must not receive the verifier's withheld behavioral checks.");
    } else if (step === 1) {
      heading(root, "02 · The investigator", "What did the model actually observe?", inv.root_cause || "No root-cause explanation recorded");
      const facts = add(root, "div", "proof-facts");
      fact(facts, "Model", inv.model);
      fact(facts, "Model requests", inv.requests);
      fact(facts, "Investigation uncertainty", inv.uncertainty || "Not recorded");
      const transcript = Array.isArray(inv.transcript) ? inv.transcript : [];
      const list = add(root, "ol", "proof-trace");
      for (const item of transcript) {
        const label = item.kind === "tool"
          ? "Read-only: " + String(item.name || "evidence probe").replaceAll("_"," ")
          : "Model decision: " + String(item.decision || "unspecified");
        const li = add(list, "li", "", label);
        add(li, "small", "", item.kind === "tool" ? "Evidence ID: " + (item.evidence_id || "not given")
          : "Cited: " + (Array.isArray(item.evidence_ids) ? item.evidence_ids.join(", ") : "none"));
      }
      if (!transcript.length) add(root, "p", "proof-context", "No read-only tool transcript was included in this record.");
    } else if (step === 2) {
      const proposal = inv.proposal;
      heading(root, "03 · The proposal", proposal ? "A candidate fix, not an approved repair" : "The model abstained",
        proposal ? "The model's suggested edit is not an instruction to execute. Independent checks determine acceptance." :
          "No patch was proposed. This unsuccessful investigation is preserved.");
      const facts = add(root, "div", "proof-facts");
      fact(facts, "Decision", proposal ? "Proposed" : "No patch");
      fact(facts, "Target", proposal?.target_file || "None");
      fact(facts, "Execution authority", "None — read-only replay");
      if (proposal && typeof proposal.replacement === "string") {
        add(root, "p", "proof-eyebrow", "Recorded candidate file contents");
        add(root, "pre", "proof-code", proposal.replacement.slice(0,2400));
      }
    } else if (step === 3) {
      heading(root, "04 · The evidence gate", "A passing public test isn't the final verdict",
        "The recorded verifier separates defect reproduction, the visible regression and independent behavior.");
      if (!v) {
        add(root, "p", "proof-outcome neutral", "ABSTAINED · No candidate entered verification.");
      } else {
        const list = add(root, "div", "proof-check-list");
        const a = status(list, "Original defect reproduced", "ASSERT_FAIL", v.before_public?.status);
        const b = status(list, "Visible regression repaired", "PASS", v.after_public?.status);
        const c = status(list, "Independent behavioral checks", "PASS", v.after_hidden?.status);
        const consistent = result !== "VERIFIED" || (a && b && c);
        const outcome = add(root, "div", "proof-outcome " + (result === "VERIFIED" && consistent ? "good" : "bad"));
        add(outcome, "strong", "", consistent ? result.replaceAll("_"," ") : "EVIDENCE MISMATCH — NOT QUALIFIED");
        add(outcome, "p", "", result === "REJECTED_FALSE_GREEN" && b && !c
          ? "The visible regression passed, but independent behavior failed. Bravon rejected the false green."
          : result === "VERIFIED" && consistent
            ? "All three recorded test stages met their expectations. This remains fixture-specific evidence."
            : "A model assertion is insufficient without the required verification evidence.");
      }
    } else {
      heading(root, "05 · The trust boundary", "What this run establishes—and what it does not",
        "A recorded local model investigation is distinct from the separate official hosted Muse experiment.");
      const facts = add(root, "div", "proof-facts");
      fact(facts, "Recorded outcome", result.replaceAll("_"," "));
      fact(facts, "Source model", inv.model);
      fact(facts, "Network for verifier", v?.network ?? "Not recorded");
      fact(facts, "Evidence envelope", current.evidence_envelope ? "Recorded HMAC evidence" : "Not available");
      add(root, "p", "proof-context", "HMAC can detect tampering for parties without the key; it is not independent hardware attestation. The verified software repair record here is not the official Muse recovery used by Immortality.");
      add(root, "p", "proof-eyebrow", "Separate official Muse experiment — not this model run");
      add(root, "p", "proof-context", "The repository documents one operator-reported official Meta Muse Spark 1.3 DNS recovery using seven hosted requests and an accepted evidence gate. The private source record is not published in this tour, and its provenance is not independently attested here.");
      add(root, "p", "proof-context", "Immortality has separately demonstrated one bounded DNS rule transfer using an operator-held local report. Its public viewer never authenticates the origin of an uploaded file.");
      const muse=add(root,"a","proof-continue","View the separate official Muse evidence →");
      muse.href="/muse";
      const cta = add(root, "a", "proof-continue", "Explore Immortality's separate experiment →");
      cta.href = "/assets/immortality.html";
    }
  }

  function verificationStatus(v,field) {
    const value = v?.[field]?.status;
    return typeof value === "string" && value.length <= 40 ? value : "MISSING";
  }
  function checkComparisonRecord(detail,summary) {
    if (!detail || detail.schema !== "bravon.meta-investigation.v1" ||
        detail.investigation?.case_id !== summary.case_id ||
        detail.investigation?.model !== summary.model ||
        detail.verification?.verdict !== summary.verdict) {
      throw new Error("Published case and detailed evidence disagree");
    }
    const v = detail.verification;
    if (verificationStatus(v,"before_public") !== "ASSERT_FAIL" ||
        verificationStatus(v,"after_public") !== "PASS") {
      throw new Error("Selected comparison does not establish the visible test passed");
    }
    const hidden = verificationStatus(v,"after_hidden");
    if ((summary.verdict === "VERIFIED" && hidden !== "PASS") ||
        (summary.verdict === "REJECTED_FALSE_GREEN" && hidden === "PASS")) {
      throw new Error("Recorded independent behavior contradicts the advertised verdict");
    }
  }
  function renderComparison() {
    if (!comparison) return;
    const root = $("proof-journey-content");
    root.replaceChildren();
    heading(root, "COMPARATIVE EVIDENCE · TWO DIFFERENT FIXTURES",
      "The same green check can hide a different outcome.",
      "These are two separate saved cases, not alternate patches for the same incident. The comparison demonstrates what independent tests reveal; it is not a controlled experiment or an estimate of model accuracy.");
    const cards = add(root, "div", "proof-compare-identities");
    const entries = [
      ["Rejected false green", comparison.rejected],
      ["Verified repair", comparison.verified]
    ];
    for (const [label,entry] of entries) {
      const card = add(cards,"section","proof-compare-case");
      add(card,"span","proof-eyebrow",label);
      add(card,"strong","",knownCases[entry.detail.investigation.case_id]?.[0] || entry.detail.investigation.case_id);
      add(card,"small","",entry.summary.model + " · " + entry.summary.id);
    }
    const table = add(root,"table","proof-compare-table");
    const thead=add(table,"thead");
    const head=add(thead,"tr");
    for(const title of ["Recorded verification stage","Rejected repair","Verified repair"]) {
      add(head,"th","",title);
    }
    const tbody=add(table,"tbody");
    const checks=[
      ["Original defect reproduced","before_public","ASSERT_FAIL"],
      ["Visible test after patch","after_public","PASS"],
      ["Independent behavior","after_hidden","PASS"]
    ];
    for(const [label,key,expected] of checks) {
      const tr=add(tbody,"tr");
      add(tr,"th","",label);
      for(const entry of [comparison.rejected,comparison.verified]) {
        const observed=verificationStatus(entry.detail.verification,key);
        const compact = key === "before_public"
          ? (observed === "ASSERT_FAIL" ? "REPRODUCED" : "NOT REPRODUCED")
          : (observed === "PASS" ? "PASS" : observed === "MISSING" ? "MISSING" : "FAIL");
        const cell=add(tr,"td",observed===expected?"proof-cell-passed":"proof-cell-failed",compact);
        cell.setAttribute("data-check",observed===expected?"passed":"failed");
        cell.setAttribute("title","Raw recorded status: "+observed);
        cell.setAttribute("aria-label",compact+"; raw recorded status: "+observed);
      }
    }
    const conclusion=add(root,"div","proof-outcome bad");
    add(conclusion,"strong","","Why one repair was rejected");
    add(conclusion,"p","","Both recorded patches passed their visible regressions. Only the verified repair also passed independent behavioral tests. Bravon rejected the other repair instead of treating the green regression as sufficient proof.");
    add(root,"p","proof-context","Both runs were produced using local Meta open-weight models. They are distinct from the separate official hosted Muse DNS experiment; neither report establishes broad production reliability or independent third-party attestation.");
    const link=add(root,"a","proof-continue","Next: inspect Immortality's separate DNS transfer →");
    link.href="/assets/immortality.html";
  }
  async function compare() {
    if (comparing) return open(chosen);
    const attempt=++generation;
    comparing=true;
    comparison=null;
    current=null;
    currentSummary=null;
    renderControls();
    info("Loading two separate recorded outcomes for comparison…");
    try {
      if (!summaries) {
        const payload=await readJSON("/api/hackathon/runs");
        if (!Array.isArray(payload.runs)) throw new Error("Evidence index has unexpected format");
        summaries=payload.runs;
      }
      const pairs={};
      for (const [key,verdict] of [["rejected","REJECTED_FALSE_GREEN"],["verified","VERIFIED"]]) {
        const summary=summaries.find(run=>run.verdict===verdict);
        if (!summary || !/^[a-z0-9-]{1,120}$/.test(summary.id)) {
          throw new Error("Missing or invalid recorded " + verdict.toLowerCase() + " example");
        }
        const detail=await readJSON("/api/hackathon/runs/"+encodeURIComponent(summary.id));
        if (generation !== attempt) return;
        checkComparisonRecord(detail,summary);
        pairs[key]={summary,detail};
      }
      if (generation !== attempt) return;
      comparison=pairs;
      renderControls();
      renderComparison();
    } catch (error) {
      if (generation !== attempt) return;
      comparing=false;
      comparison=null;
      info("Comparison unavailable: " + (error?.message || "Unknown error") +
           ". No missing or contradictory evidence was promoted into a result.");
      renderControls();
    }
  }
  async function open(outcome) {
    if (outcome && !outcomes.includes(outcome)) return;
    chosen = outcome || chosen;
    resetState();
    const id = ++generation;
    renderControls();
    info("Loading the saved " + chosen.replaceAll("_"," ").toLowerCase() + " evidence…");
    try {
      if (!summaries) {
        const index = await readJSON("/api/hackathon/runs");
        if (!Array.isArray(index.runs)) throw new Error("Evidence index has an unexpected format");
        summaries = index.runs;
      }
      const summary = summaries.find(item => item.verdict === chosen);
      if (!summary) throw new Error("No recorded example with this outcome is available");
      if (!/^[a-z0-9-]{1,120}$/.test(summary.id)) throw new Error("Invalid recorded run identifier");
      const detail = await readJSON("/api/hackathon/runs/" + encodeURIComponent(summary.id));
      if (id !== generation) return;
      if (detail.schema !== "bravon.meta-investigation.v1" ||
          !detail.investigation || detail.investigation.case_id !== summary.case_id ||
          (detail.verification?.verdict || "ABSTAINED") !== summary.verdict) {
        throw new Error("The saved evidence does not match its index; no verdict will be displayed");
      }
      currentSummary = summary;
      current = detail;
      render();
    } catch(error) {
      if (id !== generation) return;
      info("This example could not be loaded: " + (error?.message || "Unknown evidence error") +
        ". No test result or model action has been inferred.");
      renderControls();
    }
  }
  function go(index) {
    if (!current || !Number.isInteger(index) || index < 0 || index >= steps.length) return;
    step = index;
    render();
  }
  document.addEventListener("click", event => {
    const choice = event.target.closest("[data-proof-choice]");
    if (choice) { open(choice.dataset.proofChoice); return; }
    const compareControl=event.target.closest("[data-proof-compare]");
    if(compareControl){compare();return;}
    const stage = event.target.closest("[data-proof-stage]");
    if (stage) { go(Number(stage.dataset.proofStage)); return; }
    const nav = event.target.closest("[data-proof-direction]");
    if (nav) go(step + Number(nav.dataset.proofDirection));
  });
  window.BravonProofJourney = Object.freeze({open, go, compare});
})();