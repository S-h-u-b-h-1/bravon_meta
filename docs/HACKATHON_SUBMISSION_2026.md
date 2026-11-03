# Bravon submission draft

Status: prepared, not submitted. The privacy-preserving public source snapshot
is published at `https://github.com/S-h-u-b-h-1/bravon_meta`. The owner supplied
the demo URL on November 3, 2026; external playback and portal submission must
still be verified and authorized by the owner.

## Project description

Bravon is a verification-first AI engineering platform. It reproduces a real
technical defect, gives a bounded Meta model allowlisted read-only diagnostics,
reviews the proposed repair, applies it only to a disposable isolated copy, and
independently runs both the original regression and hidden behavioral tests.
Incomplete repairs are rejected even when the visible test passes. Accepted
repairs produce a reproducible evidence record with execution identity,
environment digest, timings, test outcomes, and an authenticated digest.

## Challenge fit

**Push the Frontier:** Bravon adds an independent behavioral verdict to
AI-assisted repair. Model confidence and model context cannot decide whether a
repair is verified.

## Meta AI tooling

- Actual model: Meta Llama 3.1 8B open weights, run locally through Ollama.
- Model context: bounded problem metadata plus allowlisted `read_target`,
  `read_public_test`, and `read_failure` observations.
- Excluded: hidden tests, expected repairs, signing secrets, shell access,
  arbitrary URLs, dependency installation, and verification verdicts.
- Recorded usage: 9 investigations, 45 model requests, 16,199 input tokens,
  1,791 output tokens, and $0.00 API cost.
- Recorded outcome: 4 proposals independently verified, 2 false-green proposals
  independently rejected, and 3 genuine abstentions retained as unsuccessful
  runs.
- **Separate operator-reported official Meta Model API trial (October 28):**
  Meta Muse Spark 1.3 used 7 hosted requests, 3,831 input tokens and 1,638
  output tokens to propose `restore_dns` for a real disposable CoreDNS fault.
  Bravon's evidence gate accepted it; independent Docker clone verification
  passed 5/5, followed by separately approved 5/5 active recovery. Private
  JSON proof remains on the operator's Mac; it is not yet a publicly reviewed
  third-party attestation or proof of general model reliability.
- Baseten is a separate provider and was not used for this successful trial.
  The older local Llama 3.1 runs and the Muse Model API trial must remain
  separately identified, with neither counted as automatic production repair.
- The October 27 live Participant Guide allows Meta open-weight models in Stage
  One, so the local Llama 3.1 runs satisfy the stated baseline Meta requirement.
  They do not qualify the project for the separate Muse-only open-weight bonus.

## Judging alignment

The live Participant Guide is authoritative for submission planning and
weights Impact 30%, Meta AI Tooling 25%, Technical Depth and Execution 20%,
and Demo 25%.

- Impact: prevents plausible but incomplete AI repairs from being
  promoted into engineering systems.
- Meta AI Tooling: an actual Meta model controls a bounded evidence
  investigation and produces structured repairs without seeing hidden tests.
- Technical Depth and Execution: isolated reproduction, independent
  tests, false-green rejection, signed evidence, and reproducible evaluation.
- Demo: one three-minute workflow covering verified repair, rejected
  repair, abstention, and three technical domains.

## Architecture

```text
Browser (public, read-only)
        |
        v
FastAPI evidence API ----> committed evidence records

Local operator boundary
  Meta model -> bounded diagnostic protocol -> repair proposal
                                                |
                                                v
  first-party fixture -> isolated Docker worker -> public regression
                                         |       -> hidden behavior tests
                                         v
                              HMAC evidence envelope
```

The worker uses a digest-pinned Python image, disabled network, read-only root,
non-root UID, dropped capabilities, no-new-privileges, and CPU, memory, PID,
time, output, and patch-size limits. Public Vercel endpoints cannot execute or
mutate investigations.

## Pre-existing versus hackathon-built

The pre-existing code is frozen at tag
`hackathon-start-baseline-2026-10-26`, commit
`b0dd80f721d28d36e9e680bb18181ae20d4d0347`. It includes the simulated incident
lab, infrastructure Docker lab, evidence-envelope primitives, differential
validation, and synthetic evaluation tools.

Hackathon work begins at commit `b8304dd` and is itemized in
`docs/HACKATHON_BUILD_LEDGER.md`: software, data, and infrastructure fixtures,
the isolated repair worker, false-green tests, HMAC-authenticated evaluation
reports, bounded Meta investigation, actual local model runs, and the public
evidence workspace.

## Reproducible results

- Offline repair candidates: 6.
- Complete repairs independently verified: 3.
- Incomplete repairs rejected: 3.
- False-repair acceptance rate: 0% in this six-candidate fixture evaluation.
- Evidence coverage: signed report envelopes for 6 of 6 candidates.
- Recorded offline worker time: 8,429 ms for the saved evaluation run.
- Actual Meta runs: 9; 4 verified proposals, 2 false-green rejections, and 3
  abstentions.
- Root-cause accuracy: 9 of 9 under the disclosed case-marker rubric.
- Proposal repair success rate: 4 of 6.
- Abstention quality: 0 of 3 because the model identified the cause but did not
  provide substantive uncertainty; each response said “Not applicable.”
- Actual-run evidence coverage: all 9 runs requested source, public test, and
  reproduced failure evidence.
- Timed end-to-end benchmark: 44,483 ms across one fresh actual run per domain
  (software 18,501 ms; data 12,348 ms; infrastructure 13,634 ms). Each total
  includes original failure reproduction, model investigation, and candidate
  verification.
- Verified candidate worker times: 1,822 ms and 1,872 ms.
- Hosted CI gate: current PR #11 jobs fail before runner execution with zero
  steps because the account has a `$0` Actions spending budget. Issue #12
  remains open. Exact-source local evidence is preserved separately and is not
  represented as a successful GitHub Actions run.

These figures describe only committed first-party fixtures and recorded runs;
they are not estimates of general software-repair accuracy.

## Links

- Public source snapshot: `https://github.com/S-h-u-b-h-1/bravon_meta`
- Product: `https://bravon-meta.vercel.app`
- Demo (owner-provided YouTube URL): `https://youtu.be/kx5_vs1fy4g`
- Video status: uploaded link supplied; signed-out playback and final verification pending.

## Limitations and required confirmations

- The new evaluated demo covers three first-party Python fixtures: software,
  data processing, and infrastructure configuration. The older Docker incident
  lab predates kickoff and is disclosed separately as pre-existing.
- Arbitrary third-party repositories remain blocked.
- HMAC authenticates possession of a shared runner secret; it is not public-key
  attestation or proof of organizational independence.
- Earlier Llama 3.1 investigations used local open weights, not Muse Spark.
  The separate October 28 Docker DNS investigation used official Meta Muse
  Spark 1.3; neither constitutes qualifying proof for the open-weight bonus.
- The public deployment is intentionally read-only and cannot run workers.
- Track, team list, signed-out video playback, release/provenance disclosures,
  and final portal submission require owner confirmation.

## Immortality: physically tested DNS antibody transfer (October 29)

The hackathon-period Nightmare & Antibody Engine compiles a **fixed,
non-executable** invariant from one previously recovered, evidence-gated
official Muse Spark 1.3 Docker incident. It re-evaluates that rule against a
separate System B with different private network settings.

**Owner-reported live Docker experiment:** A harmful DNS candidate was BLOCKED
by the transferred policy; a disposable clone showed DNS and end-to-end HTTP
failures. A legitimate change to healthy standby routing was ALLOWED and
its separate clone passed all five checks. Active System B remained healthy,
and temporary Docker resources were cleaned. On October 29, the operator
ran 10/10 new audit tests and saved an offline audit result
\`STRUCTURALLY_CONSISTENT_CONTROLLER_REPORT\`. The user also visibly opened
the locally exported report in the read-only Immortality viewer.

**Evidence type:** private, self-digested operator-controller records on the
owner's Mac; not cryptographically authenticated external attestation.
One recorded real Muse diagnosis plus two deterministic destination candidates
does **not** establish general LLM success rates, unseen-fault discovery,
global protection or arbitrary cross-customer transfer. The physical transfer
is **DNS only**; proxy and backend antibody families have offline tests.

**Privacy:** source and transfer reports are not committed to GitHub, hosted
on Vercel, or shared with other users. The viewer processes a locally selected
report inside the browser. Publishing even redacted reports requires a separate
owner-controlled privacy review.

See \`docs/IMMORTALITY.md\` and the replacement Immortality-first
\`docs/HACKATHON_DEMO_SCRIPT_3_MIN.md\` for reproduction and the new demo plan.

## Submission and video release blockers

- Final video: owner-supplied URL `https://youtu.be/kx5_vs1fy4g` references
  the new narrated animated demo; verify signed-out access, real captions and
  the recorded-versus-live disclosures before submission.
- Repository: `S-h-u-b-h-1/bravon_meta` is the public history-free source
  snapshot. Its private provenance cannot be independently inferred from the
  public root commit; the original development repository remains private.
- Portal: accepted participant status, personal responses, rights/consent and
  submission fields must be confirmed in the authenticated portal. The form
  has not been submitted by this assistant.
- Judging: use the Participant Guide's 30/25/20/25 rubric. A November 1 live
  recheck confirmed that it matches the Official Rules; the earlier
  equal-weight interpretation was incorrect.
