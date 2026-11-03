"use strict";
/** No-network, no-Docker DOM contract tests for minimized cloud receipt inspection. */
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {createHash,webcrypto}=require("node:crypto");
const {TextEncoder}=require("node:util");
const vm=require("node:vm");
const script=fs.readFileSync(path.join(__dirname,"..","web","remote-evidence.js"),"utf8");
const CHECKS=["dns-record","proxy-route","upstream-health","e2e","standby"];
const LIMITATIONS="GitHub Actions runner and Docker controller report, not external attestation. Only predefined disposable DNS/proxy/backend faults, deterministic repair rules and five fixed health checks. No Meta Muse inference, customer infrastructure access, general self-healing or production certification.";

function canonical(input){
  if(Array.isArray(input))return input.map(canonical);
  if(input&&typeof input==="object"){
    const out={};
    for(const key of Object.keys(input).sort())out[key]=canonical(input[key]);
    return out;
  }
  return input;
}
function seal(result){
  delete result.content_digest;
  result.content_digest=createHash("sha256").update(JSON.stringify(canonical(result))).digest("hex");
  return result;
}
function receipt(){
  const before=CHECKS.map(id=>({id,passed:!["dns-record","e2e"].includes(id)}));
  const healthy=CHECKS.map(id=>({id,passed:true}));
  return seal({
    schema:"bravon.remote-docker-qualification.v1",
    execution_mode:"GH_HOSTED_DISPOSABLE_DOCKER",
    model_inference:"NONE_RULE_BASED_ONLY",
    report_status:"QUALIFIED_CONTROLLER_REPORT",
    run:{repository:"S-h-u-b-h-1/bravon",run_id:"123456",attempt:"1",commit:"a".repeat(40)},
    requested_scenarios:["dns-drift"],
    results:[{
      scenario:"dns-drift",action:"restore_dns",result:"PASSED",
      before,sandbox_after:healthy,recovery_after:healthy,
      unapproved_repair_denied:true,stale_revision_repair_denied:true,cleanup_to_healthy:true
    }],
    five_check_invariants:CHECKS,
    raw_controller_digest:"b".repeat(64),
    limitations:LIMITATIONS
  });
}
function createBrowser(){
  const nodes=new Map();
  function element(tag){
    return {
      tag,textContent:"",hidden:false,value:"",children:[],attributes:{},className:"",
      addEventListener(name,handler){this[name]=handler;},
      setAttribute(name,value){this.attributes[name]=String(value);},
      replaceChildren(...newChildren){this.children=newChildren;},
      appendChild(child){this.children.push(child);return child;}
    };
  }
  function get(id){
    if(!nodes.has(id))nodes.set(id,element("div"));
    return nodes.get(id);
  }
  const context={document:{getElementById:get,createElement:element},
    crypto:webcrypto,TextEncoder,console};
  vm.runInNewContext(script,context,{filename:"web/remote-evidence.js"});
  async function upload(payload,filename="minimized.json"){
    const contents=typeof payload==="string"?payload:JSON.stringify(payload);
    const file={name:filename,size:Buffer.byteLength(contents),async text(){return contents;}};
    await get("remote-receipt-file").change({target:{files:[file]}});
  }
  return {get,upload};
}

test("no remote evidence is invented before local import",()=>{
  const page=createBrowser();
  assert.match(page.get("remote-receipt-status").textContent,/No remote qualification report loaded/);
  assert.equal(page.get("remote-receipt-view").hidden,true);
});
test("strict receipt renders a real-probe story only as controller evidence",async()=>{
  const page=createBrowser();
  await page.upload(receipt());
  assert.equal(page.get("remote-receipt-view").hidden,false);
  assert.match(page.get("remote-receipt-status").textContent,/does not independently prove/);
  assert.match(page.get("remote-report-label").textContent,/NOT an independent attestation/);
  assert.match(page.get("remote-report-count").textContent,/1 \/ 1/);
  assert.equal(page.get("remote-report-scenarios").children.length,1);
  assert.match(page.get("remote-report-run").textContent,/123456/);
  assert.match(page.get("remote-report-limitations").textContent,/No Meta Muse inference/);
});
test("tampering without recomputing digest is rejected",async()=>{
  const page=createBrowser(),r=receipt();
  r.results[0].before[0].passed=true;
  await page.upload(r);
  assert.match(page.get("remote-receipt-status").textContent,/Receipt rejected/);
  assert.equal(page.get("remote-receipt-view").hidden,true);
});
test("fabricated safe baseline is rejected even with a new digest",async()=>{
  const page=createBrowser(),r=receipt();
  r.results[0].before=CHECKS.map(id=>({id,passed:true}));
  await page.upload(seal(r));
  assert.match(page.get("remote-receipt-status").textContent,/Initial failed probes contradict/);
  assert.equal(page.get("remote-receipt-view").hidden,true);
});
test("model inference, fake runner, cleanup and extra unsafe fields fail closed",async()=>{
  const page=createBrowser(),r=receipt();
  r.model_inference="META_MUSE";
  await page.upload(seal(r));
  assert.match(page.get("remote-receipt-status").textContent,/cannot claim verified remote/);
  r.model_inference="NONE_RULE_BASED_ONLY";
  r.results[0].cleanup_to_healthy=false;
  await page.upload(seal(r));
  assert.match(page.get("remote-receipt-status").textContent,/cleanup safety check/);
  r.results[0].cleanup_to_healthy=true;
  r.private_docker_log="secret";
  await page.upload(seal(r));
  assert.match(page.get("remote-receipt-status").textContent,/Unexpected receipt fields/);
});
test("wrong unknown scenario and provenance refused",async()=>{
  const page=createBrowser(),r=receipt();
  r.results[0].action="failover";
  await page.upload(seal(r));
  assert.match(page.get("remote-receipt-status").textContent,/Scenario\/action/);
  r.results[0].action="restore_dns";
  r.run.repository="unknown/repo";
  await page.upload(seal(r));
  assert.match(page.get("remote-receipt-status").textContent,/Unknown runner identity/);
});
test("oversize and malformed input fail without echoing private file contents",async()=>{
  const page=createBrowser();
  await page.upload("{INVALID SECRET 12345}");
  assert.match(page.get("remote-receipt-status").textContent,/Invalid JSON receipt/);
  assert.doesNotMatch(page.get("remote-receipt-status").textContent,/SECRET/);
  const huge={name:"big.json",size:120000,async text(){throw Error("Must not read");}};
  await page.get("remote-receipt-file").change({target:{files:[huge]}});
  assert.match(page.get("remote-receipt-status").textContent,/smaller than 100 KB/);
});
test("local file picker and clear control are keyboard-operable",async()=>{
  const page=createBrowser();
  let opened=false;
  page.get("remote-receipt-file").click=()=>{opened=true;};
  page.get("remote-choose-receipt").click();
  assert.equal(opened,true);
  await page.upload(receipt());
  page.get("remote-reset-receipt").click();
  assert.equal(page.get("remote-receipt-view").hidden,true);
  assert.equal(page.get("remote-receipt-file").value,"");
});
test("viewer contains no calls to remote mutation, model or arbitrary scripting",()=>{
  assert.doesNotMatch(script,/\bfetch\s*\(/);
  assert.doesNotMatch(script,/\.innerHTML\s*=/);
  assert.doesNotMatch(script,/\b(?:eval|Function|localStorage|sessionStorage)\s*\(/);
  assert.match(script,/crypto\.subtle\.digest/);
  assert.match(script,/file\.text\(\)/);
});
