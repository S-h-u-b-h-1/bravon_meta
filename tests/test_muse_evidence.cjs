"use strict";
/** Read-only Muse receipt viewer tests; no Docker, network or hosted inference. */
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {createHash,webcrypto}=require("node:crypto");
const {TextEncoder}=require("node:util");
const vm=require("node:vm");
const source=fs.readFileSync(path.join(__dirname,"..","web","muse-evidence.js"),"utf8");
const LIMITATIONS="Operator-controlled, self-digested evidence; NOT third-party or hardware attestation. One fixed DNS invariant and two predetermined System B candidates. No global immunity or production prevention established.";
const MODEL="hosted-muse:official-meta:muse-spark-1.3";

function canonical(input) {
  if(Array.isArray(input))return input.map(canonical);
  if(input && typeof input==="object"){
    const result={};
    for(const key of Object.keys(input).sort())result[key]=canonical(input[key]);
    return result;
  }
  return input;
}
function signed(payload) {
  const contents={...payload};
  delete contents.content_digest;
  payload.content_digest=createHash("sha256").update(JSON.stringify(canonical(contents))).digest("hex");
  return payload;
}
function receipt() {
  return signed({
    schema:"bravon.jury-muse-receipt.v1",
    evidence_level:"OFFLINE_CONTROLLER_CONSISTENCY_ONLY",
    source:{
      model:MODEL,scenario:"dns-drift",proposed_action:"restore_dns",
      hosted_requests:7,read_only_evidence_items:6,cited_evidence_items:3,
      gate_allowed:true,sandbox_checks_passed:5,active_recovered:true
    },
    transfer:{
      rule_family:"dns-gateway-binding",destination:"B",
      dangerous_policy:"BLOCK",dangerous_failed_checks:["dns-record","e2e"],
      legitimate_policy:"ALLOW",legitimate_checks_passed:5,
      active_preserved:true,cleanup_recorded:true
    },
    links:{source_recovery_digest:"a".repeat(64),destination_report_digest:"b".repeat(64)},
    limitations:LIMITATIONS
  });
}
function harness(){
  const elements=new Map();
  function el(id) {
    if(!elements.has(id))elements.set(id,{
      textContent:"",value:"",addEventListener(kind,callback){this[kind]=callback;}
    });
    return elements.get(id);
  }
  vm.runInNewContext(source,{
    document:{getElementById:el},
    crypto:webcrypto,
    TextEncoder,
    console
  },{filename:"web/muse-evidence.js"});
  async function upload(doc,name="audited-muse.json"){
    const body=typeof doc==="string"?doc:JSON.stringify(doc);
    const file={name,size:Buffer.byteLength(body),async text(){return body;}};
    await el("muse-evidence-file").change({target:{files:[file]}});
  }
  return {el,upload};
}

test("documented summary is honest without a file",()=>{
  const h=harness();
  assert.match(h.el("muse-receipt-status").textContent,/No local evidence file/);
  assert.match(h.el("muse-evidence-mode").textContent,/DOCUMENTED IN REPOSITORY/);
  assert.match(h.el("muse-boundary-detail").textContent,/not independent third-party attestation/);
});
test("valid locally selected receipt displays the bounded recorded chain",async()=>{
  const h=harness();
  await h.upload(receipt());
  assert.match(h.el("muse-receipt-status").textContent,/Structure and receipt content digest matched/);
  assert.match(h.el("muse-evidence-mode").textContent,/NOT INDEPENDENTLY ATTESTED/);
  assert.equal(h.el("muse-model-requests").textContent,"7");
  assert.equal(h.el("muse-probes").textContent,"6");
  assert.equal(h.el("muse-citations").textContent,"3");
  assert.equal(h.el("muse-danger-decision").textContent,"BLOCK");
  assert.equal(h.el("muse-safe-decision").textContent,"ALLOW");
  assert.match(h.el("muse-boundary-detail").textContent,/cannot authenticate the origin/);
});
test("tampering with a saved value without recomputing digest is rejected",async()=>{
  const h=harness(),tampered=receipt();
  tampered.source.hosted_requests=9;
  await h.upload(tampered);
  assert.match(h.el("muse-receipt-status").textContent,/Receipt rejected: Receipt was altered/);
  assert.match(h.el("muse-evidence-mode").textContent,/DOCUMENTED IN REPOSITORY/);
  assert.equal(h.el("muse-model-requests").textContent,"7");
});
test("even a re-digested false-green destination is rejected",async()=>{
  const h=harness(),tampered=receipt();
  tampered.transfer.active_preserved=false;
  signed(tampered);
  await h.upload(tampered);
  assert.match(h.el("muse-receipt-status").textContent,/Destination experimental outcome is incomplete/);
});
test("wrong model and schema cannot masquerade as official Muse",async()=>{
  const h=harness(),bad=receipt();
  bad.source.model="llama3.1:8b";signed(bad);
  await h.upload(bad);
  assert.match(h.el("muse-receipt-status").textContent,/Not a qualified official Muse/);
  bad.source.model=MODEL;bad.schema="bravon.unknown.v1";signed(bad);
  await h.upload(bad);
  assert.match(h.el("muse-receipt-status").textContent,/Unsupported jury receipt schema/);
});
test("malformed and oversized files fail closed without revealing report strings",async()=>{
  const h=harness();
  await h.upload("<script>attack</script>");
  assert.match(h.el("muse-receipt-status").textContent,/Receipt rejected/);
  const huge={name:"too-big.json",size:64_001,async text(){throw Error("MUST NOT READ");}};
  await h.el("muse-evidence-file").change({target:{files:[huge]}});
  assert.match(h.el("muse-receipt-status").textContent,/under 64 KB/);
});
test("reset clears the selected receipt and restores clear provenance",async()=>{
  const h=harness();
  await h.upload(receipt());
  h.el("muse-reset").click();
  assert.match(h.el("muse-evidence-mode").textContent,/DOCUMENTED IN REPOSITORY/);
  assert.equal(h.el("muse-evidence-file").value,"");
});
test("inspector has no network writes, eval or unsafe HTML interpolation",()=>{
  assert.doesNotMatch(source,/\bfetch\s*\(/);
  assert.doesNotMatch(source,/\.innerHTML\s*=/);
  assert.doesNotMatch(source,/\b(?:eval|Function|localStorage|sessionStorage)\s*\(/);
  assert.match(source,/crypto\.subtle\.digest/);
  assert.match(source,/file\.text\(\)/);
});


test("file picker is keyboard-operable through a real button",()=>{
  const h=harness();
  let invoked=false;
  h.el("muse-evidence-file").click=()=>{invoked=true;};
  h.el("muse-choose").click();
  assert.equal(invoked,true);
});
