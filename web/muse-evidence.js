(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const SCHEMA = "bravon.jury-muse-receipt.v1";
  const MODEL = "hosted-muse:official-meta:muse-spark-1.3";
  const EVIDENCE_LEVEL = "OFFLINE_CONTROLLER_CONSISTENCY_ONLY";
  const LIMITATIONS = "Operator-controlled, self-digested evidence; NOT third-party or hardware attestation. One fixed DNS invariant and two predetermined System B candidates. No global immunity or production prevention established.";
  const MAX_BYTES = 64_000;
  const fields = {
    root: ["schema","evidence_level","source","transfer","links","limitations","content_digest"],
    source: ["model","scenario","proposed_action","hosted_requests","read_only_evidence_items","cited_evidence_items","gate_allowed","sandbox_checks_passed","active_recovered"],
    transfer: ["rule_family","destination","dangerous_policy","dangerous_failed_checks","legitimate_policy","legitimate_checks_passed","active_preserved","cleanup_recorded"],
    links: ["source_recovery_digest","destination_report_digest"]
  };
  let revision = 0;
  const text = (id, value) => { $(id).textContent = String(value); };
  function sameFields(value, names) {
    return value && typeof value === "object" && !Array.isArray(value)
      && Object.keys(value).length === names.length
      && names.every(key => Object.prototype.hasOwnProperty.call(value,key));
  }
  function count(value, low, high) {
    return Number.isInteger(value) && value >= low && value <= high;
  }
  function assertion(yes, message) {
    if (!yes) throw new Error(message);
  }
  // Equivalent ordering to Python's json.dumps(sort_keys=True, separators=(",",":"))
  // for the fixed ASCII-only, integer/bool receipt schema.
  function canonical(value) {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value === "object") {
      const sorted = {};
      for (const key of Object.keys(value).sort()) sorted[key] = canonical(value[key]);
      return sorted;
    }
    return value;
  }
  async function contentDigest(payload) {
    const encoded = new TextEncoder().encode(JSON.stringify(canonical(payload)));
    const data = await crypto.subtle.digest("SHA-256",encoded);
    return [...new Uint8Array(data)].map(v=>v.toString(16).padStart(2,"0")).join("");
  }
  async function validate(input) {
    assertion(sameFields(input,fields.root),"Unrecognized receipt fields");
    assertion(input.schema === SCHEMA,"Unsupported jury receipt schema");
    assertion(input.evidence_level === EVIDENCE_LEVEL,"Unrecognized evidence provenance level");
    assertion(input.limitations === LIMITATIONS,"Required limitations were changed or removed");
    assertion(sameFields(input.source,fields.source),"Source evidence fields are incomplete");
    assertion(sameFields(input.transfer,fields.transfer),"Transfer evidence fields are incomplete");
    assertion(sameFields(input.links,fields.links),"Source/transfer linkage is incomplete");

    const a = input.source, b = input.transfer;
    assertion(a.model === MODEL && a.scenario === "dns-drift" &&
      a.proposed_action === "restore_dns","Not a qualified official Muse DNS case");
    assertion(count(a.hosted_requests,1,10) &&
      count(a.read_only_evidence_items,1,12) &&
      count(a.cited_evidence_items,1,12) &&
      a.cited_evidence_items <= a.read_only_evidence_items,"Model usage/evidence counts invalid");
    assertion(a.gate_allowed === true && a.sandbox_checks_passed === 5 &&
      a.active_recovered === true,"Source gate or recovery not qualified");
    assertion(b.rule_family === "dns-gateway-binding" && b.destination === "B" &&
      b.dangerous_policy === "BLOCK" && b.legitimate_policy === "ALLOW" &&
      b.legitimate_checks_passed === 5 && b.active_preserved === true &&
      b.cleanup_recorded === true,"Destination experimental outcome is incomplete");
    assertion(Array.isArray(b.dangerous_failed_checks) &&
      b.dangerous_failed_checks.length === 2 &&
      b.dangerous_failed_checks[0] === "dns-record" &&
      b.dangerous_failed_checks[1] === "e2e","Dangerous clone's probe pattern is invalid");
    const hex = /^[a-f0-9]{64}$/;
    assertion(fields.links.every(key=>typeof input.links[key] === "string" &&
      hex.test(input.links[key])),"Missing source or transfer digest");
    assertion(typeof input.content_digest === "string" &&
      hex.test(input.content_digest),"Receipt content digest missing");
    const copy = {...input};
    delete copy.content_digest;
    assertion(await contentDigest(copy) === input.content_digest,
      "Receipt was altered after offline export");
    return input;
  }
  function restoreSummary() {
    text("muse-receipt-status","Documented summary shown. No local evidence file has been selected.");
    text("muse-evidence-mode","DOCUMENTED IN REPOSITORY · PRIVATE SOURCE NOT LOADED");
    text("muse-model-requests","7");
    text("muse-probes","Private");
    text("muse-citations","Private");
    text("muse-model",MODEL);
    text("muse-scenario","DNS record drift · disposable Docker");
    text("muse-action","restore_dns");
    text("muse-gate","Documented acceptance · receipt not loaded");
    text("muse-sandbox","Documented 5/5 checks · not authenticated here");
    text("muse-recovered","Operator-reported · not authenticated here");
    text("muse-rule-name","dns-gateway-binding");
    text("muse-danger-decision","BLOCK");
    text("muse-safe-decision","ALLOW");
    text("muse-danger-checks","Documented failed probes: DNS resolution, end-to-end HTTP");
    text("muse-safe-checks","Documented: 5 of 5 control probes passed");
    text("muse-transfer-note","The source and transfer outcome is documented in owner-controlled reports. No private JSON is published here, and the browser does not independently attest the experiment.");
    text("muse-boundary-detail","The existing offline auditor checks internal report consistency and model citations. Even a passing audit is not independent third-party attestation of Meta inference or Docker execution. One DNS rule and two predetermined changes do not demonstrate global immunity, production reliability or general autonomous repair.");
  }
  function render(receipt) {
    const a=receipt.source,b=receipt.transfer;
    text("muse-evidence-mode","LOCAL MINIMIZED RECEIPT · CONTENT DIGEST MATCHED · NOT INDEPENDENTLY ATTESTED");
    text("muse-model-requests",a.hosted_requests);
    text("muse-probes",a.read_only_evidence_items);
    text("muse-citations",a.cited_evidence_items);
    text("muse-model",a.model);
    text("muse-scenario","DNS record drift · disposable Docker");
    text("muse-action",a.proposed_action);
    text("muse-gate","Accepted according to the selected controller receipt");
    text("muse-sandbox",a.sandbox_checks_passed + " / 5 recorded clone checks");
    text("muse-recovered","Reported recovered in disposable System A");
    text("muse-rule-name",b.rule_family);
    text("muse-danger-decision",b.dangerous_policy);
    text("muse-safe-decision",b.legitimate_policy);
    text("muse-danger-checks","Recorded failed checks: DNS resolution, end-to-end HTTP");
    text("muse-safe-checks",b.legitimate_checks_passed + " / 5 recorded control checks passed");
    text("muse-transfer-note","The selected receipt reports an offline audit and System B preservation/cleanup. No fresh Docker or Meta call occurred; this browser checks only the minimized receipt's fields and content digest, not its origin.");
    text("muse-boundary-detail",LIMITATIONS + " The browser cannot authenticate the origin of the selected JSON, the controller's self-reported execution, or the original source/transfer digests.");
  }
  async function readLocal(file) {
    const id=++revision;
    restoreSummary();
    if (!file) {
      text("muse-receipt-status","No file selected; showing documented public summary.");
      return;
    }
    try {
      assertion(typeof file.name === "string" && /\.json$/i.test(file.name),
        "Choose a .json file exported by the offline jury receipt generator");
      assertion(count(file.size,1,MAX_BYTES),"Receipt must be a nonempty JSON file under 64 KB");
      const raw=await file.text();
      assertion(raw.length <= MAX_BYTES,"Receipt exceeds the safe viewer limit");
      const payload=await validate(JSON.parse(raw));
      if (id !== revision) return;
      render(payload);
      text("muse-receipt-status","Loaded from this browser only: "+file.name+
        ". Structure and receipt content digest matched. This is NOT third-party attestation.");
    } catch(error) {
      if (id !== revision) return;
      restoreSummary();
      text("muse-receipt-status","Receipt rejected: "+(error?.message||"Unrecognized format")+
        ". Showing documented public summary, not a qualified imported result.");
    }
  }
  function reset() {
    revision++;
    $("muse-evidence-file").value="";
    restoreSummary();
    text("muse-receipt-status","Documented summary shown. No local evidence file has been selected.");
  }
  $("muse-choose").addEventListener("click",()=>{$("muse-evidence-file").click();});
  $("muse-evidence-file").addEventListener("change",event=>{
    const file = event.target.files?.[0];
    event.target.value = ""; // Permit selecting the same receipt again after a rejection.
    return readLocal(file);
  });
  $("muse-reset").addEventListener("click",reset);
  restoreSummary();
})();
