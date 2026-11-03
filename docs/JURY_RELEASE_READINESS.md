# Bravon jury release-readiness audit

**Scope:** guided public evidence viewer, simulation, local Docker screen, Immortality viewer, model-trial report and cross-lab navigation.  
**Basis:** source review, API and Node regression tests, and a real headless Chromium smoke run against a loopback FastAPI server with Vercel-style write guards. This does **not** replace independent manual accessibility/security testing.

## Product principle

**Trust only what the recorded evidence supports.** A verified local Llama repair, a browser-only simulation, a separately authorized official Meta Muse investigation and an operator-reported Immortality transfer are different categories of evidence. The UI must not collapse them into a generic “AI success.”

## Findings and remediation

| Priority | Observation | Action | Verification |
| --- | --- | --- | --- |
| P0 | Original jury action jumped directly into a verdict, without explaining investigation or proposal | Five-stage Proof Journey loads the actual published case and reveals the evidence chain | Node simulated-browser tests and server-side GET contract |
| P0 | A summary label could be mistaken for proof without validating the detailed record | Detail schema, case ID and verdict must match the index; mismatches refuse to display a qualification | Negative mismatch test |
| P0 | Public site cannot execute real Docker or paid Muse; visitor might expect it to | Clear read-only labels, documented local-only operator boundary and no-setup evidence replay | Explicit GET-only test and 403 backend mutation tests |
| P1 | Mobile route navigation is duplicated | Hide legacy mobile route strip only when the shared route switcher is present | Static route and fallback inspection |
| P1 | Shared navigation was inserted before the accessibility skip link | Keep skip link first in document keyboard order | Source-level navigation contract |
| P1 | The proof narrative had no shareable entry | Add `/#tour` route and active navigation state | Navigation contract tests |
| P1 | A local Llama run could be mistaken for official Meta Muse evidence | Model identity and the distinction between separate experiments appear in the final evidence step | Tour narrative contract |
| P0 | Reduced-motion CSS accidentally forced off-canvas sidebar transforms to zero, blocking taps on mobile | Preserve functional transforms while disabling animations | Real Chromium reproduction and rerun |
| P1 | The repair comparison was hard to scan on narrow screens | Show compact PASS/FAIL/REPRODUCED statuses; retain raw verifier status as accessible detail | Browser screenshot and verification tests |
| P1 | Simulation topology extended beyond the viewport without a scrolling cue | Add an explicit swipe hint and mobile scroll affordance | Mobile browser smoke |
| P1 | Three levels of navigation competed for attention in the jury journey | Use a focused reading view with stage navigation and the shared global route bar | Responsive browser smoke |
| P0 | The documented official Meta Muse experiment was invisible in the public experience | Add read-only /muse source chain with separately labelled recorded facts; offline audited receipt exporter and strict local-file viewer | Python audit/privacy tests, Node receipt tampering tests, desktop/mobile browser checks |

## Quality standards and limits

- **Accessibility:** target WCAG 2.2 AA behaviors where applicable: keyboard navigation, visible focus, readable contrast, input target sizing, semantic headings, status announcements, and reduced-motion support. Actual screen-reader and rendered contrast testing remain required.
- **Security:** use OWASP ASVS 5.0 as a verification checklist rather than claiming certification. Recorded model text is inserted with `textContent`, not interpreted as HTML; the tour performs GET requests only. Keep Docker and all paid inference protected by server-side authorization.
- **Evidence integrity:** read-only schema/identity checks protect the presentation from accidental mismatch; they do not cryptographically authenticate independent execution.
- **Operational readiness:** production release requires a reviewed exact commit, passing CI, a READY preview, and independent visual/browser checks.

## Automated checks

```bash
node --check web/proof-journey.js
node --check web/muse-evidence.js
node --test tests/test_proof_journey.cjs tests/test_bravon_ui.cjs tests/test_immortality_viewer.cjs tests/test_muse_evidence.cjs
python -m pytest -q tests/test_frontend_pages.py tests/test_jury_receipt.py
# GitHub Actions browser-smoke job additionally installs Playwright Chromium.
python qa/browser_smoke.py
```

GitHub Actions additionally runs the full Python suite, fixed benchmark fixtures and model-wire tests.

### Executed browser automation

The `browser-smoke` GitHub Actions job starts FastAPI bound to 127.0.0.1 with `VERCEL=1` and real Docker disabled. It drives Chromium at **1440×900 desktop** and **390×844 mobile** (reduced motion), captures screenshots, and checks:

- Real published rejected/verified evidence and a side-by-side comparison, including the difference between visible and independent tests
- Mobile sidebar positioning, open/close interactions, horizontal overflow and legacy route-bar visibility
- Browser-only DNS injection → deterministic analysis → verification → approved simulated recovery
- Immortality's explicitly synthetic guided example, Docker control restrictions and Model Trials mock page
- Official Muse documentary evidence, in-memory receipt import and self-digest check, invalid/tampered receipt rejection, no raw private files or API inference
- Public API denial of mutation requests (HTTP 403), no model/Docker calls from the jury walkthrough and no uncaught browser errors

These are **automated smoke tests**, not a broad cross-browser, accessibility or security certification. Screenshots are retained for seven days in a private GitHub Actions artifact.

## Manual acceptance matrix (not yet executed)

| Route / state | Desktop | Mobile | Keyboard | Failure behavior |
| --- | --- | --- | --- | --- |
| `/#tour` — rejected and verified paths | Pending | Pending | Pending | Missing record and altered verdict must refuse acceptance |
| `/` — initial overview and history | Pending | Pending | Pending | Empty/failed evidence fetch must be visible |
| `/simulation` — DNS/proxy/backend synthetic failures | Pending | Pending | Pending | No writes to public backend |
| `/docker` — local-only guard explanation | Pending | Pending | Pending | Public Docker POST remains HTTP 403 |
| `/assets/immortality.html` — synthetic and local file | Pending | Pending | Pending | Invalid/private evidence must not be promoted as authenticated |
| `/muse` — documented source and local jury receipt | Pending | Pending | Pending | Wrong model, altered receipt and fake Docker results must fail closed |
| `/model-trials` — sample scorecard | Pending | Pending | Pending | Must identify mock versus actual inference |

Use at least 390×844, 768×1024 and 1440×900 CSS-pixel viewports, reduced-motion preference, tab-only navigation, and the browser console/network log. Do not record a pass without observed evidence.

## Executed PR #11 browser and Model Trials accessibility follow-up (October 31, 2026)

An isolated non-persistent Vercel Sandbox was populated with the **private PR #11
source**, then started the real Bravon FastAPI app on loopback with
\`VERCEL=1\` and Docker mutation controls disabled. The test environment
installed Playwright 1.58.0 and its headless Chromium dependencies; network
access was set to **deny-all before test execution**.

**Successfully executed:** \`PYTHONPATH=/vercel PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64 python3 qa/browser_smoke.py\`.

- The complete Chromium smoke script passed: saved-case Proof Journey,
  verified/false-green comparison, mobile sidebar and overflow guards,
  synthetic DNS recovery, local-only Docker restrictions, read-only remote
  receipt validation and tamper refusal, documented Muse receipt, synthetic
  Immortality viewer and static Model Trials page.
- All local fixture reports used for this test were **synthetic CI fixtures**;
  no real Docker daemon was started, no hosted Meta model was called and no
  actual owner-held source/transfer reports were imported.
- Additional static-page defect found and fixed: archived Model Trials lacked
  a first-tab skip link/main landmark and its static nav did not expose
  \`/muse\`. It now has a keyboard-visible skip link, a \`main#main\`
  landmark, 44-pixel navigation targets, reduced-motion/focus styles and an
  explicit link to the official Muse evidence page.
- **Post-fix rerun passed:** three
  \`tests/test_model_trials_accessibility.cjs\` tests (3/3) plus the complete
  original Chromium \`qa/browser_smoke.py\` suite, now including keyboard
  focus on the first Model Trials tab stop and a 390px mobile overflow check.
- A later local axe-core 4.10.3 scan covered all seven jury routes at
  390×844, 768×1024 and 1440×900. It first found insufficient breadcrumb
  contrast and a non-focusable horizontal topology region on `/simulation`.
  Commit `e326e8c` fixed both, and the 21-combination rerun reported **zero
  WCAG 2/2.1 A/AA or WCAG 2.2 AA violations**. This is still not WCAG
  certification; manual VoiceOver review remains a release gate.
- A separate local WebKit 2359 smoke pass covered the same 21 route/viewport
  combinations with HTTP success, no page errors and no horizontal overflow.
  It used a temporary matching Playwright client and changed no project
  dependency. This is bounded engine coverage, not manual Safari certification.

The hosted GitHub Actions CI associated with current PR #11 revisions remains
blocked before runner execution because the owner account has a `$0` Actions
spending budget and cannot add a payment method or increase it. Issue #12 stays
open. Isolated local validation on commit
`689a74dda31762850d00f122d5e7d66f179877b3` passed 464 non-Docker Python
3.12 tests with 2 skips, 50 Node tests, Chromium and WebKit browser QA, and 42
axe route/viewport checks. Reports, logs, versions, and hashes are retained in
`docs/evidence/local-release-2026-11-01-689a74d/`. This evidence **does not
change GitHub CI status**, execute the 11 pinned-worker Docker tests, perform a
physical cloud Docker qualification, or authorize production promotion.

## Outstanding release blockers

1. **Independent manual visual and accessibility QA remains.** Local Chromium and WebKit smoke plus axe checks are green, but a human still needs to inspect keyboard focus, VoiceOver/screen-reader behavior and failure-path messaging. The authenticated deployment preview may require Vercel access.
2. **Official Meta Muse source report stays private.** The /muse page now shows only documented public facts until an owner-generated offline audit receipt is selected locally. The receipt has not been created or approved for public publication here; controller self-digests are not external attestation. See docs/JURY_MUSE_RECEIPT.md.
3. **Immortality remains a bounded DNS experiment.** Its controller report is self-digested, not independently attested. Do not claim arbitrary cross-machine immunity.
4. **Production Docker is not available on Vercel.** This is an architectural restriction, not a UI bug. Any future remote runner needs authenticated isolation, resource limits and its own security review.
5. **Publication/security/license/submission approvals are separate gates.** Do not make the private repository public merely because tests pass.

## Jury message

“Bravon rejects AI repairs that merely turn the public test green. Inspect a recorded failing and passing repair side by side. A separate official Meta Muse experiment extends this idea by converting a qualified DNS recovery into a bounded, portable rule tested on another isolated system.”

This is a product demonstration statement, not a general prevention-rate or global novelty claim.
