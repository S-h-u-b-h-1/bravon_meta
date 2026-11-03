"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "..", "web", "proof-journey.js"), "utf8");

function fakeRecord(verdict, caseId) {
  const accepted = verdict === "VERIFIED";
  return {
    schema: "bravon.meta-investigation.v1",
    generated_at: "2026-10-27T10:00:00Z",
    inference: "ACTUAL_LOCAL_META_OPEN_WEIGHTS",
    investigation: {
      case_id: caseId, model: "llama3.1:8b", requests: 3,
      root_cause: "Observed root cause", uncertainty: "Not independently attested",
      proposal: {target_file:"repair.py", replacement:"check = 'passed'"},
      transcript: [
        {kind:"tool", name:"read_failure", evidence_id:"failure"},
        {kind:"final", decision:"propose", evidence_ids:["failure"]}
      ]
    },
    verification: {
      verdict, network:"none",
      before_public:{status:"ASSERT_FAIL"},
      after_public:{status:"PASS"},
      after_hidden:{status:accepted ? "PASS" : "ASSERT_FAIL"}
    },
    evidence_envelope:{runner_id:"local-sandbox"}
  };
}
function fakeElement(tag) {
  const attrs = new Map();
  const classes = new Set();
  return {
    tag, dataset:{}, children:[], textContent:"", className:"", disabled:false, href:"",
    classList:{toggle(name,on) {if(on)classes.add(name);else classes.delete(name);}},
    setAttribute(name,value){attrs.set(name,String(value));},
    removeAttribute(name){attrs.delete(name);},
    getAttribute(name){return attrs.get(name);},
    appendChild(child){this.children.push(child);return child;},
    replaceChildren(...children){this.children=children;},
  };
}
function textTree(el) {return [el.textContent, ...el.children.map(textTree)].join(" ");}

function setup(overrides={}) {
  const nodes=new Map();
  function $(id) {if(!nodes.has(id))nodes.set(id,fakeElement("div"));return nodes.get(id);}
  const stages=Array.from({length:5},(_,i)=>{
    const button=fakeElement("button");button.dataset.proofStage=String(i);return button;
  });
  const callbacks={};
  const rejectedId="local-meta-falsegreen";
  const acceptedId="local-meta-verified";
  const index={runs:[
    {id:rejectedId,case_id:"software-refund-negative-quantity",model:"llama3.1:8b",verdict:"REJECTED_FALSE_GREEN"},
    {id:acceptedId,case_id:"data-final-row-and-decimals",model:"llama3.1:8b",verdict:"VERIFIED"}
  ]};
  const calls=[];
  async function fetch(url,options) {
    calls.push({url,options});
    let data;
    if(url==="/api/hackathon/runs") data=index;
    else if(url.endsWith(rejectedId))data=fakeRecord("REJECTED_FALSE_GREEN","software-refund-negative-quantity");
    else if(url.endsWith(acceptedId))data=fakeRecord("VERIFIED","data-final-row-and-decimals");
    else return {ok:false,status:404,async json(){return {detail:"Missing"};}};
    if(overrides.mismatch && url.endsWith(acceptedId))data.verification.verdict="ABSTAINED";
    return {ok:true,async json(){return data;}};
  }
  const doc={
    getElementById:$,
    createElement:fakeElement,
    querySelectorAll(selector){return selector==="[data-proof-stage]"?stages:[];},
    addEventListener(name,cb){callbacks[name]=cb;}
  };
  const window={};
  vm.runInNewContext(source,{window,document:doc,fetch,URL,encodeURIComponent,console},{filename:"proof-journey.js"});
  return {api:window.BravonProofJourney,$,calls,stages,callbacks};
}

test("false-green journey displays the failing independent check from a saved record", async()=>{
  const app=setup();
  await app.api.open("REJECTED_FALSE_GREEN");
  assert.equal(app.$("proof-choice-REJECTED_FALSE_GREEN").getAttribute("aria-pressed"),"true");
  assert.match(textTree(app.$("proof-journey-content")),/Negative refund quantity/);
  app.api.go(3);
  const content=textTree(app.$("proof-journey-content"));
  assert.match(content,/REJECTED FALSE GREEN/);
  assert.match(content,/independent behavior failed/i);
  assert.match(content,/ASSERT_FAIL/);
  assert.equal(app.stages[3].getAttribute("aria-current"),"step");
  assert.equal(app.$("proof-journey-progress").textContent,"Step 4 of 5");
  assert.deepEqual(app.calls.map(x=>x.options.method),["GET","GET"]);
});
test("a verified record is qualified only when its three independent stages agree",async()=>{
  const app=setup();
  await app.api.open("VERIFIED");
  app.api.go(3);
  const content=textTree(app.$("proof-journey-content"));
  assert.match(content,/VERIFIED/);
  assert.match(content,/All three recorded test stages/);
  assert.equal(app.$("proof-journey-next").disabled,false);
  app.api.go(4);
  assert.match(textTree(app.$("proof-journey-content")),/distinct from the separate official hosted Muse/);
  assert.equal(app.$("proof-journey-next").disabled,true);
});
test("mismatched saved details fail closed without displaying a verified verdict",async()=>{
  const app=setup({mismatch:true});
  await app.api.open("VERIFIED");
  assert.match(textTree(app.$("proof-journey-content")),/does not match its index/);
  assert.equal(app.$("proof-journey-next").disabled,true);
});
test("journey never writes untrusted report data into HTML or invokes a mutation endpoint",()=>{
  assert.doesNotMatch(source,/\.innerHTML\s*=/);
  assert.doesNotMatch(source,/method:\s*["'](?:POST|PUT|PATCH|DELETE)["']/i);
  assert.match(source,/document\.createElement/);
  assert.match(source,/\.textContent\s*=/);
  assert.match(source,/bravon\.meta-investigation\.v1/);
});


test("comparison displays both published visible passes and the divergent hidden evidence",async()=>{
  const app=setup();
  await app.api.compare();
  assert.equal(app.$("proof-compare").getAttribute("aria-pressed"),"true");
  assert.equal(app.$("proof-journey-progress").textContent,"Side-by-side evidence");
  const text=textTree(app.$("proof-journey-content"));
  assert.match(text,/Negative refund quantity/);
  assert.match(text,/Dropped final revenue row/);
  assert.match(text,/The same green check can hide a different outcome/);
  assert.match(text,/Both recorded patches passed their visible regressions/);
  assert.match(text,/REPRODUCED/);
  assert.match(text,/FAIL/);
  assert.equal(app.$("proof-journey-back").hidden,true);
  assert.equal(app.$("proof-journey-next").hidden,true);
  assert.match(text,/PASS/);
  assert.match(text,/different fixtures|separate saved cases/i);
  assert.deepEqual(app.calls.map(x=>x.options.method),["GET","GET","GET"]);
  assert.equal(app.$("proof-journey-next").disabled,true);
});

test("comparison fails closed when a detail verdict contradicts the published index",async()=>{
  const app=setup({mismatch:true});
  await app.api.compare();
  assert.match(textTree(app.$("proof-journey-content")),/Comparison unavailable/);
  assert.match(textTree(app.$("proof-journey-content")),/evidence disagree/);
  assert.equal(app.$("proof-compare").getAttribute("aria-pressed"),"false");
});

test("comparison can return to a single saved case without leaking comparison state",async()=>{
  const app=setup();
  await app.api.compare();
  await app.api.compare();
  assert.equal(app.$("proof-compare").getAttribute("aria-pressed"),"false");
  assert.match(textTree(app.$("proof-journey-content")),/Negative refund quantity/);
  assert.equal(app.$("proof-journey-next").disabled,false);
});
