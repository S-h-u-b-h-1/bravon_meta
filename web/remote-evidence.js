(() => {
  "use strict";
  // Read-only, strictly constrained inspection. No network, Docker or model requests.
  const $ = id => document.getElementById(id);
  const SCHEMA = "bravon.remote-docker-qualification.v1";
  const LIMITATIONS = "GitHub Actions runner and Docker controller report, not external attestation. Only predefined disposable DNS/proxy/backend faults, deterministic repair rules and five fixed health checks. No Meta Muse inference, customer infrastructure access, general self-healing or production certification.";
  const SCENARIOS = ["dns-drift", "proxy-misroute", "backend-outage"];
  const ACTIONS = ["restore_dns", "restore_proxy", "failover"];
  const CHECKS = ["dns-record", "proxy-route", "upstream-health", "e2e", "standby"];
  const BEFORE_FAILURES = {
    "dns-drift":["dns-record","e2e"],
    "proxy-misroute":["proxy-route","upstream-health","e2e"],
    "backend-outage":["upstream-health","e2e"]
  };
  const REQUIRED = {
    root: ["schema","execution_mode","model_inference","report_status","run","requested_scenarios","results","five_check_invariants","raw_controller_digest","limitations","content_digest"],
    run: ["repository","run_id","attempt","commit"],
    result: ["scenario","action","result","before","sandbox_after","recovery_after","unapproved_repair_denied","stale_revision_repair_denied","cleanup_to_healthy"],
    check: ["id","passed"]
  };
  const MAX_RECEIPT_BYTES = 100_000;
  let selection = 0;
  const text = (id,value) => {$(id).textContent=String(value);};
  const exact = (object,keys) => object && typeof object==="object" && !Array.isArray(object)
    && Object.keys(object).length===keys.length
    && keys.every(key=>Object.prototype.hasOwnProperty.call(object,key));
  const assert = (valid,message) => {if(!valid)throw new Error(message);};
  const clearStatus = () => {
    $("remote-receipt-view").hidden = true;
    $("remote-report-scenarios").replaceChildren();
    text("remote-report-label","Reported qualification");
    text("remote-report-count","—");
    text("remote-report-run","—");
    text("remote-report-limitations","—");
  };
  function canonical(value) {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value==="object") {
      const result={};
      for(const key of Object.keys(value).sort())result[key]=canonical(value[key]);
      return result;
    }
    return value;
  }
  async function digest(value) {
    const buffer=new TextEncoder().encode(JSON.stringify(canonical(value)));
    const hash=await crypto.subtle.digest("SHA-256",buffer);
    return Array.from(new Uint8Array(hash),x=>x.toString(16).padStart(2,"0")).join("");
  }
  function checks(rows,expectedHealthy,scenario,stage) {
    assert(Array.isArray(rows)&&rows.length===5,"Expected five health probes at "+stage);
    const statuses={};
    for(const row of rows){
      assert(exact(row,REQUIRED.check),"Invalid probe fields");
      assert(CHECKS.includes(row.id)&&!Object.prototype.hasOwnProperty.call(statuses,row.id)
             && typeof row.passed==="boolean","Invalid or repeated probe identity");
      statuses[row.id]=row.passed;
    }
    assert(CHECKS.every(id=>Object.prototype.hasOwnProperty.call(statuses,id)),"Missing fixed health checks");
    if(expectedHealthy){
      assert(CHECKS.every(id=>statuses[id]),"Reported recovery still contains failed health checks");
    }else{
      const expected=BEFORE_FAILURES[scenario];
      const failed=CHECKS.filter(id=>statuses[id]===false);
      assert(Array.isArray(expected) && failed.length===expected.length &&
             expected.every(id=>failed.includes(id)),
        "Initial failed probes contradict the claimed injected scenario");
    }
    return statuses;
  }
  async function validate(receipt) {
    assert(exact(receipt,REQUIRED.root),"Unexpected receipt fields");
    assert(receipt.schema===SCHEMA,"Unsupported remote qualification schema");
    assert(receipt.execution_mode==="GH_HOSTED_DISPOSABLE_DOCKER" &&
           receipt.model_inference==="NONE_RULE_BASED_ONLY" &&
           receipt.report_status==="QUALIFIED_CONTROLLER_REPORT",
           "Receipt cannot claim verified remote deterministic Docker results");
    assert(receipt.limitations===LIMITATIONS,"Required evidence limitations were changed");
    assert(exact(receipt.run,REQUIRED.run),"Missing fixed runner identity");
    assert(receipt.run.repository==="S-h-u-b-h-1/bravon" &&
           /^[0-9]{1,20}$/.test(receipt.run.run_id) &&
           /^[0-9]{1,3}$/.test(receipt.run.attempt) &&
           /^[a-f0-9]{40}$/.test(receipt.run.commit),"Unknown runner identity");
    const listed=receipt.requested_scenarios;
    assert(Array.isArray(listed)&&[1,3].includes(listed.length),"Unsupported scenario list");
    assert(listed.every(x=>SCENARIOS.includes(x))&&new Set(listed).size===listed.length,
           "Invalid or repeated scenario");
    if(listed.length===3)assert(listed.every((x,i)=>x===SCENARIOS[i]),"Multi-scenario order differs");
    assert(Array.isArray(receipt.results)&&receipt.results.length===listed.length,
           "Incomplete qualification scenarios");
    assert(Array.isArray(receipt.five_check_invariants) &&
           CHECKS.every((x,i)=>receipt.five_check_invariants[i]===x) &&
           receipt.five_check_invariants.length===5,"Unexpected safety check identities");
    for(let i=0;i<listed.length;i++){
      const row=receipt.results[i];
      assert(exact(row,REQUIRED.result),"Missing scenario evidence fields");
      assert(row.scenario===listed[i] && row.action===ACTIONS[SCENARIOS.indexOf(row.scenario)] &&
             row.result==="PASSED","Scenario/action/qualification mismatch");
      assert(row.unapproved_repair_denied===true &&
             row.stale_revision_repair_denied===true &&
             row.cleanup_to_healthy===true,"Repair authorization or cleanup safety check failed");
      checks(row.before,false,row.scenario,"before");
      checks(row.sandbox_after,true,row.scenario,"sandbox");
      checks(row.recovery_after,true,row.scenario,"recovery");
    }
    const hex=/^[a-f0-9]{64}$/;
    assert(typeof receipt.raw_controller_digest==="string" &&
           hex.test(receipt.raw_controller_digest) &&
           typeof receipt.content_digest==="string" &&
           hex.test(receipt.content_digest),"Missing report/receipt digests");
    const original={...receipt}; delete original.content_digest;
    assert(await digest(original)===receipt.content_digest,"Receipt content digest does not match");
    return receipt;
  }
  function add(parent,tag,className,value){
    const element=document.createElement(tag);
    if(className)element.className=className;
    if(value!==undefined)element.textContent=String(value);
    parent.appendChild(element);
    return element;
  }
  function render(receipt) {
    clearStatus();
    text("remote-report-label","Qualified per selected controller receipt · NOT an independent attestation");
    text("remote-report-count",receipt.results.length+" / "+receipt.requested_scenarios.length+" recorded scenarios");
    text("remote-report-run","GitHub Actions "+receipt.run.run_id+" · commit "+receipt.run.commit.slice(0,9));
    text("remote-report-limitations",receipt.limitations);
    const root=$("remote-report-scenarios");
    for(const item of receipt.results){
      const card=add(root,"article","remote-scenario");
      const title=add(card,"div","remote-scenario-heading");
      add(title,"strong","",item.scenario.replaceAll("-"," "));
      add(title,"span","remote-scenario-status","RECORDED PASS");
      const note=add(card,"p","remote-scenario-copy","Rule-based action: "+item.action+" · no model inference");
      note.setAttribute("data-lab","disposable");
      const grid=add(card,"div","remote-three-stages");
      for(const [heading,rows] of [
        ["Injected failure",item.before],
        ["Independent clone",item.sandbox_after],
        ["Active recovery",item.recovery_after]
      ]){
        const stage=add(grid,"div","remote-stage");
        add(stage,"small","",heading);
        const passed=rows.filter(x=>x.passed).length;
        add(stage,"strong","",passed+" / 5");
        add(stage,"span","",heading==="Injected failure"?"Fault reproduced":"Recorded healthy");
      }
      add(card,"p","remote-scenario-proof","Rejected unapproved/stale repairs · returned to healthy baseline.");
    }
    $("remote-receipt-view").hidden=false;
  }
  async function readLocal(file){
    const id=++selection;
    clearStatus();
    if(!file){text("remote-receipt-status","No receipt selected. The public website cannot start real Docker.");return;}
    try{
      assert(typeof file.name==="string" && /\.json$/i.test(file.name),
             "Choose a JSON qualification receipt");
      assert(Number.isInteger(file.size) && file.size>0 && file.size<=MAX_RECEIPT_BYTES,
             "Receipt must be smaller than 100 KB");
      const raw=await file.text();
      assert(raw.length<=MAX_RECEIPT_BYTES,"Receipt exceeds fixed parsing limit");
      let value;
      try{value=JSON.parse(raw);}catch(_){throw new Error("Invalid JSON receipt");}
      const checked=await validate(value);
      if(id!==selection)return;
      render(checked);
      text("remote-receipt-status","Local receipt accepted: structure and content digest matched. This does not independently prove GitHub/Docker execution.");
    }catch(error){
      if(id!==selection)return;
      clearStatus();
      text("remote-receipt-status","Receipt rejected: "+(error?.message||"Invalid evidence")+
        ". No remote Docker qualification has been inferred.");
    }
  }
  function reset(){
    selection++;
    $("remote-receipt-file").value="";
    clearStatus();
    text("remote-receipt-status","No remote qualification report loaded. Real Docker execution is not available to public visitors.");
  }
  $("remote-choose-receipt").addEventListener("click",()=>{$("remote-receipt-file").click();});
  $("remote-receipt-file").addEventListener("change",event=>{
    const file=event.target.files?.[0];
    event.target.value="";
    return readLocal(file);
  });
  $("remote-reset-receipt").addEventListener("click",reset);
  reset();
})();