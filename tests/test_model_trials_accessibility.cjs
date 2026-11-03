"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const html=fs.readFileSync(path.join(__dirname,"..","docs","model-trials-v081-DEMO-MOCK.html"),"utf8");

test("model evidence begins with a keyboard-accessible skip link and main landmark",()=>{
  assert.match(html,/<a class="model-skip" href="#main">Skip to model evidence<\/a>/);
  assert.match(html,/<main id="main" class="wrap" tabindex="-1">/);
  assert.ok(html.indexOf('class="model-skip"')<html.indexOf('<nav class="model-nav"'));
  assert.match(html,/\.model-skip:focus-visible\{top:12px\}/);
  assert.match(html,/:where\(a,summary\):focus-visible/);
  assert.match(html,/@media\(prefers-reduced-motion:reduce\)/);
});

test("model-trial navigation reaches the same core Bravon routes as the other labs",()=>{
  assert.match(html,/<nav class="model-nav" aria-label="Switch Bravon labs"/);
  for(const route of ["/","/#tour","/simulation","/docker","/muse",
                     "/assets/immortality.html","/model-trials"]){
    assert.ok(html.includes('href="'+route+'"'),"Missing model-trial navigation route: "+route);
  }
  assert.match(html,/href="\/model-trials" aria-current="page"/);
  assert.match(html,/\.model-nav a\{[^}]*min-height:44px/);
});

test("model evidence separates actual Meta records from archived synthetic controls",()=>{
  assert.match(html,/SYNTHETIC ONLY · NO REPAIR/);
  assert.match(html,/Muse Spark evidence/);
  assert.match(html,/Recorded Llama investigations/);
  assert.match(html,/AI proposals/);
  assert.match(html,/Legacy evaluation fixture/);
  assert.match(html,/Recorded model investigations/);
  assert.match(html,/Meta Llama 3\.1 8B/i);
  assert.match(html,/45 local model requests/);
  assert.match(html,/FALSE-GREEN REJECTIONS/);
  assert.match(html,/ABSTENTIONS/);
  assert.match(html,/Meta Muse Spark 1\.3/);
  assert.match(html,/not third-party attestation/);
  assert.match(html,/OFFLINE MOCK \/ NOT A REAL MODEL RESULT/);
  assert.doesNotMatch(html,/injected-test-provider/);
  assert.doesNotMatch(html,/ProofOps/);

  assert.match(html,/meta http-equiv="Content-Security-Policy"/);
  assert.doesNotMatch(html,/<script\b/i);
  assert.doesNotMatch(html,/<iframe\b/i);
  assert.match(html,/<\/main><\/body><\/html>\s*$/);
});
