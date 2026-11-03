# Bravon hackathon build ledger

Official kickoff used for this ledger: October 26, 2026 at 12:00 PM ET
(9:30 PM IST). The immutable pre-kickoff boundary is tag
`hackathon-start-baseline-2026-10-26` at commit
`b0dd80f721d28d36e9e680bb18181ae20d4d0347`.

## Existing before kickoff

- Deterministic in-memory incident simulation and dashboard.
- Local disposable Docker infrastructure lab for DNS, proxy and backend faults.
- Read-only investigation protocol and evidence gates.
- Differential regression record validation.
- HMAC evidence envelopes and durable atomic SQLite replay protection.
- Signed execution-manifest validation primitives.
- Synthetic and model-evaluation tooling documented by the baseline tag.

These capabilities are pre-existing support code. They must not be presented in
the hackathon demo as functionality built during the event.

## Built during the hackathon

| Started (IST) | Capability | Evidence |
| --- | --- | --- |
| 2026-10-26 21:35 | First-party software and data defect fixtures | `fixtures/hackathon/` |
| 2026-10-26 21:35 | Bounded Docker verifier with no network, read-only root, non-root identity, CPU/memory/PID/time/output limits | `proofops/hackathon_worker.py` |
| 2026-10-26 21:35 | Independent hidden behavior tests that reject incomplete repairs | `tests/test_hackathon_worker.py` |
| 2026-10-26 21:48 | HMAC-authenticated verification-report envelopes bound to the worker image | `proofops/hackathon_worker.py` |
| 2026-10-26 21:48 | Reproducible offline evaluation with explicit zero-call Meta status | `proofops/hackathon_eval.py`, `docs/evidence/hackathon-evaluation.json` |
| 2026-10-26 22:03 | Bounded read-only software/data investigation protocol with structured repairs and uncertainty | `proofops/hackathon_investigation.py` |
| 2026-10-26 22:10 | Actual local Meta Llama 3.1 investigations, including preserved abstentions and independently verified repairs | `docs/evidence/local-meta-*.json` |
| 2026-10-26 22:31 | Public read-only evidence workspace with actual run history, repair review, verification output and export | `web/hackathon.*`, `proofops/api.py` |
| 2026-10-26 22:31 | Public mutation denial and browser security headers | `proofops/api.py`, `tests/test_api.py` |
| 2026-10-26 22:43 | Three-minute script, submission draft and public-release checklist | `docs/HACKATHON_DEMO_SCRIPT_3_MIN.md`, `docs/HACKATHON_SUBMISSION_2026.md`, `docs/PUBLIC_RELEASE_CHECKLIST.md` |
| 2026-10-27 00:54 | Infrastructure configuration fixture and actual Meta-proposed false-green repair rejected by independent hardening tests | `fixtures/hackathon/infrastructure_healthcheck/`, `docs/evidence/local-meta-infrastructure-investigation.json` |
| 2026-10-27 01:01 | Reproducible Meta-run evaluation with disclosed root-cause and abstention rubrics | `proofops/hackathon_eval.py`, `docs/evidence/meta-evaluation.json` |
| 2026-10-27 01:05 | End-to-end timing evidence for one fresh actual Meta run in each domain | `docs/evidence/local-meta-timed-*.json` |
| 2026-10-27 01:43 | Local 162.32-second actual-workflow demo draft with reviewed media manifest | `docs/HACKATHON_VIDEO_DRAFT.md` |

| 2026-10-28 (during hackathon) | Opt-in official Meta Muse Spark 1.3 read-only investigator for disposable real Docker, separately operator-reported DNS diagnosis, evidence-gated sandbox verification and explicitly approved recovery | `proofops/hosted_muse.py`, `proofops/real_lab.py`, operator-private `hosted-muse-*-v1.json` evidence |
| 2026-10-28–29 (during hackathon) | Immortality antibody compiler and closed-form DNS/proxy/health rules; Nightmare candidate evaluator; explicitly opt-in two-system DNS experiment, redacted report and local-file viewer | `proofops/immortality.py`, `proofops/immortality_docker.py`, `web/immortality.*`, PR #4 |
| 2026-10-29 (operator-reported validation) | System B on distinct Docker subnet: proposed dangerous DNS change blocked and observed to break DNS/E2E only in a clone; legitimate standby route allowed and 5/5; active B unchanged and clone cleanup recorded; source-to-transfer JSON consistency auditor passed | `proofops/immortality_audit.py`, `tests/test_immortality_audit.py`, operator-private `antibody-real-transfer-v2.json`; not third-party attestation |
| 2026-10-29 (visual check) | Private audited JSON loaded into local-file browser viewer, showing true Meta-model and recovered DNS origin, destination topology slot, portable policy and experimental outcome | `web/immortality.js`, `tests/test_immortality_viewer.cjs`; screenshot reviewed by owner |
| 2026-10-31 | Seven-route responsive browser regression suite and accessibility fixes for breadcrumb contrast and keyboard access to the service-topology region | `qa/browser_smoke.py`, `tests/test_bravon_ui.cjs`, `web/index.html`, `web/styles.css` |
| 2026-10-31 | Qualification evidence validation made fail-closed under optimized Python, with a regression test for tampered evidence | `proofops/qualification.py`, `tests/test_qualification.py` |
| 2026-10-31 | Evidence-grounded portal copy and release checklist reconciled with the Participant Guide, current CI admission blocker and replacement-video requirement | `docs/HACKATHON_SUBMISSION_DRAFT.md`, `docs/PUBLIC_RELEASE_CHECKLIST.md` |
| 2026-10-31 | Post-Immortality 99.518-second local review video captured from the real browser workflow with system narration, English captions and a reviewed contact sheet; no upload, inference or Docker execution | local `output/hackathon-demo-v2/`, `docs/HACKATHON_VIDEO_DRAFT.md` |
| 2026-11-01 | Final demo-quality pass created readable evidence close-ups, persistent recorded-versus-live disclosure, and a privacy-minimized three-report Muse jury receipt that binds investigation, recovery and System B transfer by incident identity and digests | `proofops/jury_receipt.py`, `tests/test_jury_receipt.py`, local `output/hackathon-demo-v3/` |

First post-kickoff commit: `b8304dd` (`feat: add isolated repair verification fixtures`).

## Disclosure rule

The submission and three-minute video will show only rows in “Built during the
hackathon” as new work. Pre-existing components may be described as supporting
infrastructure and must be explicitly attributed to the frozen cutoff tag.
Private operator reports and digest links are not public attestations and must
not be uploaded to the repository or Vercel without separate review and approval.
