"use strict";
/** DOM-contract tests for the real Bravon workspace, no external dependencies.
 * This is a lightweight, no-network shell test; not a pixel-visual browser test.
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(root, "web", "hackathon.html"), "utf8");
const css = fs.readFileSync(path.join(root, "web", "hackathon-polish.css"), "utf8");
const js = fs.readFileSync(path.join(root, "web", "hackathon.js"), "utf8");
const immHtml = fs.readFileSync(path.join(root, "web", "immortality.html"), "utf8");
const immCss = fs.readFileSync(path.join(root, "web", "immortality.css"), "utf8");

function cls() {
  const set = new Set();
  return {
    add(name) { set.add(name); },
    remove(name) { set.delete(name); },
    contains(name) { return set.has(name); },
    toggle(name, forced) {
      if (forced === true) { set.add(name); return true; }
      if (forced === false) { set.delete(name); return false; }
      if (set.has(name)) { set.delete(name); return false; }
      set.add(name); return true;
    },
  };
}

function createBrowser() {
  const nodes = new Map();
  const callbacks = {};
  function node(id) {
    if (!nodes.has(id)) {
      const attrs = new Map();
      nodes.set(id, {
        id, classList: cls(), dataset: {}, textContent: "", innerHTML: "",
        hidden: false, value: "",
        setAttribute(k,v) { attrs.set(k,String(v)); },
        getAttribute(k) { return attrs.get(k); },
        removeAttribute(k) { attrs.delete(k); },
        addEventListener(event,cb) { this[event] = cb; },
        focus() { this.focused = true; },
      });
    }
    return nodes.get(id);
  }
  const names = ["overview", "tour", "local", "new", "workspace",
    "repair", "verification", "report", "history"];
  const views = names.map(name => ({dataset: {page:name}, classList:cls()}));
  const navs = names.map(name => ({
    dataset: {view:name}, classList:cls(),
    setAttribute() {}, removeAttribute() {},
  }));
  const run = {
    id: "local-meta-software-test",
    case_id: "software-refund-negative-quantity",
    verdict: "ABSTAINED",
    decision: "abstain",
    model: "llama3.1:8b",
    generated_at: "2026-10-27T10:00:00Z",
    input_tokens: 17, output_tokens: 13, cost_usd: 0,
  };
  const detail = {
    inference: "ACTUAL_LOCAL_META_OPEN_WEIGHTS",
    generated_at: run.generated_at,
    investigation: {
      case_id: run.case_id, model: run.model, proposal: null,
      requests: 1, input_tokens:17, output_tokens:13, cost_usd:0,
      root_cause:"Insufficient evidence", uncertainty:"Model abstained",
      transcript: [],
    },
    verification: null,
    evidence_envelope: null,
  };
  const fetch = async url => ({
    ok: true,
    async json() {
      return url === "/api/hackathon/runs" ?
        {runs: [run]} : detail;
    },
  });
  const doc = {
    getElementById: node, body: {classList:cls()},
    querySelectorAll(selector) {
      if (selector === ".view") return views;
      if (selector === ".nav-item") return navs;
      return [];
    },
    addEventListener(event, cb) { callbacks[event] = cb; },
    title: "",
  };
  const windowObject = {
    innerWidth: 700, scrollTo() {},
    addEventListener(event,cb) { callbacks["window:"+event] = cb; },
  };
  vm.runInNewContext(js, {
    document: doc, window: windowObject,
    history: {replaceState() {}},
    location: {hostname:"bravon-preview.vercel.app", hash:""},
    fetch, setTimeout() {}, matchMedia() {return {matches:false};},
    URL, Blob,
  }, {filename:"web/hackathon.js"});
  return {
    node, doc, views, navs, callbacks,
    async loaded() { await new Promise(resolve => setImmediate(resolve)); },
  };
}

test("workspace has semantic navigation, real Immortality shortcut and filters", () => {
  assert.match(html, /id="sidebar"/);
  assert.match(html, /id="nav-toggle"[^>]*aria-controls="sidebar"/);
  assert.match(html, /id="nav-backdrop"/);
  assert.match(html, /id="nav-close"/);
  assert.match(html, /class="rail-feature-link" href="\/assets\/immortality\.html"/);
  assert.match(html, /id="run-search"/);
  assert.match(html, /id="verdict-filter"/);
  assert.match(html, /href="\/assets\/hackathon-polish\.css"/);
  assert.match(html, /Public read-only/);
});

test("Immortality is informative before a private JSON is selected", () => {
  assert.match(immHtml, /id="hero-title"/);
  assert.match(immHtml, /id="upload-zone"/);
  assert.match(immHtml, /id="choose-report"/);
  assert.match(immHtml, /id="preview"/);
  assert.match(immHtml, /id="clear-report"/);
  assert.match(immHtml, /id="bad-checks"/);
  assert.match(immHtml, /id="good-checks"/);
  assert.match(immHtml, /No public execution/);
});

test("both shells include keyboard focus and reduced-motion support", () => {
  assert.match(css, /focus-visible/);
  assert.match(css, /max-width:820px/);
  assert.match(css, /prefers-reduced-motion:reduce/);
  assert.match(immCss, /focus-visible/);
  assert.match(immCss, /max-width:640px/);
  assert.match(immCss, /prefers-reduced-motion:reduce/);
});

test("mobile navigation opens, closes on Escape and updates accessibility state", async () => {
  const page = createBrowser();
  await page.loaded();
  page.node("nav-toggle").click();
  assert.equal(page.node("sidebar").classList.contains("open"), true);
  assert.equal(page.node("nav-toggle").getAttribute("aria-expanded"), "true");
  assert.equal(page.node("nav-backdrop").hidden, false);
  page.callbacks.keydown({key:"Escape"});
  assert.equal(page.node("sidebar").classList.contains("open"), false);
  assert.equal(page.node("nav-toggle").getAttribute("aria-expanded"), "false");
  assert.equal(page.node("nav-backdrop").hidden, true);
});

test("run-history search and verdict filtering give useful empty state", async () => {
  const page = createBrowser();
  await page.loaded();
  assert.match(page.node("history-count").textContent, /1 of 1 recorded runs/);
  assert.match(page.node("history-list").innerHTML, /local-meta-software-test/);
  page.node("run-search").value = "does-not-exist";
  page.node("run-search").input();
  assert.match(page.node("history-count").textContent, /0 of 1/);
  assert.match(page.node("history-list").innerHTML, /No recorded runs match/);
  page.node("run-search").value = "";
  page.node("verdict-filter").value = "VERIFIED";
  page.node("verdict-filter").change();
  assert.match(page.node("history-count").textContent, /0 of 1/);
  page.node("verdict-filter").value = "ABSTAINED";
  page.node("verdict-filter").change();
  assert.match(page.node("history-count").textContent, /1 of 1/);
});

test("public frontend remains read-only and avoids mutation or model endpoints", () => {
  assert.doesNotMatch(js, /fetch\s*\([^)]*(\/api\/docker\/|\/api\/repair\/)/);
  assert.doesNotMatch(js, /method:\s*["'](?:POST|PUT|PATCH|DELETE)["']/i);
  assert.doesNotMatch(immHtml, /<script[^>]+https?:\/\//);
  assert.doesNotMatch(css + immCss, /url\(https?:\/\//);
});


test("simulation and Docker pages provide consistent cross-product navigation", () => {
  const sim = fs.readFileSync(path.join(root, "web", "index.html"), "utf8");
  const docker = fs.readFileSync(path.join(root, "web", "docker.html"), "utf8");
  assert.match(sim, /href="\/assets\/immortality\.html"/);
  assert.match(docker, /href="\/assets\/immortality\.html"/);
  assert.match(sim, /class="mobile-route-nav"/);
  assert.match(docker, /class="mobile-route-nav"/);
  assert.match(sim, /href="\/assets\/lab-polish\.css"/);
  assert.match(sim, /class="topology-mobile-hint"/);
  assert.match(docker, /href="\/assets\/docker-polish\.css"/);
  assert.match(docker, /href="\/simulation">← Return to simulation<\/a>/);
  assert.match(sim, /Local operator mode/);
  assert.match(docker, /LOCAL-ONLY EXECUTION/);
});

test("simulation topology is keyboard reachable and breadcrumb text meets contrast target", () => {
  const sim = fs.readFileSync(path.join(root, "web", "index.html"), "utf8");
  const simCSS = fs.readFileSync(path.join(root, "web", "styles.css"), "utf8");
  assert.match(sim, /class="topology-scroll" tabindex="0" role="region" aria-label="Service topology"/);
  assert.match(simCSS, /\.breadcrumb\{color:#6f8792;/);
});

test("public simulation has an isolated browser demo", () => {
  const app = fs.readFileSync(path.join(root, "web", "app.js"), "utf8");
  assert.match(app, /const demoMode = publicReadOnly/);
  assert.match(app, /function demoPerform/);
  assert.match(app, /demoSnapshot/);
  assert.match(app, /if \(demoMode\)/);
});

test("legacy lab screens retain keyboard and reduced-motion styles", () => {
  const simCSS = fs.readFileSync(path.join(root, "web", "lab-polish.css"), "utf8");
  const dockerCSS = fs.readFileSync(path.join(root, "web", "docker-polish.css"), "utf8");
  for (const layer of [simCSS, dockerCSS]) {
    assert.match(layer, /focus-visible/);
    assert.match(layer, /mobile-route-nav/);
    assert.match(layer, /prefers-reduced-motion:reduce/);
  }
});


test("every main lab page exposes the shared cross-lab switcher", () => {
  const routes=["hackathon.html","index.html","docker.html","immortality.html","muse-evidence.html"];
  for(const name of routes){
    const page=fs.readFileSync(path.join(root,"web",name),"utf8");
    assert.match(page,/route-switcher\.css/);
    assert.match(page,/route-switcher\.js/);
    assert.match(page,/class="skip-link"/);
  }
  const nav=fs.readFileSync(path.join(root,"web","route-switcher.js"),"utf8");
  for(const route of ["/#tour","/muse","/simulation","/docker","/assets/immortality.html","/model-trials"]){
    assert.ok(nav.includes(route), "Missing route: "+route);
  }
  assert.match(nav,/aria-current/);
  assert.match(nav,/aria-label/);
  assert.match(nav,/skip\.insertAdjacentElement\("afterend",nav\)/);
  const sharedCSS = fs.readFileSync(path.join(root,"web","route-switcher.css"),"utf8");
  assert.match(sharedCSS,/\.bravon-route-switcher ~ \.app-shell \.mobile-route-nav/);
  for(const stylesheet of ["hackathon-polish.css","lab-polish.css","docker-polish.css","immortality.css"]){
    const text = fs.readFileSync(path.join(root,"web",stylesheet),"utf8");
    assert.doesNotMatch(text,/animation:none!important;transition:none!important;transform:none!important/);
  }
});


test("jury tour enters a separate evidence-bound route without writing to a backend", () => {
  const page=fs.readFileSync(path.join(root,"web","hackathon.html"),"utf8");
  const tour=fs.readFileSync(path.join(root,"web","proof-journey.js"),"utf8");
  assert.match(page,/data-demo-verdict="REJECTED_FALSE_GREEN"/);
  assert.match(page,/data-demo-verdict="VERIFIED"/);
  assert.match(page,/data-page="tour"/);
  assert.match(page,/id="proof-journey-content"/);
  assert.match(page,/proof-journey.css/);
  assert.match(page,/proof-journey.js/);
  assert.match(js,/window\.BravonProofJourney\.open\(guided\.dataset\.demoVerdict\)/);
  assert.match(js,/tour:"Proof Journey"/);
  assert.match(tour,/bravon\.meta-investigation\.v1/);
  assert.doesNotMatch(tour,/method:\s*["'](?:POST|PUT|PATCH|DELETE)["']/i);
});
