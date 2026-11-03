# Bravon portal-ready submission copy

Status: evidence-grounded draft, not submitted. The sanitized repository is
public and the owner supplied the YouTube video URL on November 3, 2026.
Signed-out video playback, final form review and portal submission remain owner-controlled.

## Project

**Name:** Bravon — Reliability, Proven

**Track:** Indie Developer — owner-selected; confirm the authenticated portal
selection before submission.

**Theme:** Push the Frontier

**One line:** Bravon uses Meta models to investigate technical failures, then
independently reproduces and tests proposed repairs before calling them fixed.

## Problem and solution

AI repair tools can produce plausible patches and green visible tests while
missing the real behavioral contract. Bravon gives a Meta model bounded,
read-only diagnostic tools and accepts only a structured repair proposal. A
digest-pinned, offline disposable worker reproduces the original failure,
applies the patch to a copy, runs visible and independent hidden tests, and
emits an authenticated evidence report. Model confidence never decides the
verification verdict.

## Meta technology

- Meta Llama 3.1 8B open weights through local Ollama: 9 investigations, 45
  requests, 16,199 input tokens, 1,791 output tokens and $0.00 API cost.
- Outcome: 4 proposals independently verified, 2 false-green proposals
  rejected, and 3 abstentions preserved as unsuccessful runs.
- Separate operator-reported official Meta Muse Spark 1.3 trial: 7 hosted
  requests, 3,831 input tokens and 1,638 output tokens for a disposable
  CoreDNS fault. Independent clone verification passed 5/5 before a separately
  approved active recovery passed 5/5.
- The Muse record is private, self-digested operator evidence, not external
  attestation. Baseten was not used for the successful trial, and no paid call
  is authorized by this draft.

The model sees bounded problem metadata and allowlisted source, public-test and
reproduced-failure observations. It cannot see hidden tests, expected repairs,
signing secrets, shell access, arbitrary URLs, dependency installation or the
verification verdict.

## Hackathon-period contribution

The immutable pre-kickoff baseline is tag
`hackathon-start-baseline-2026-10-26`, commit
`b0dd80f721d28d36e9e680bb18181ae20d4d0347`. It already contained the simulated
incident lab, infrastructure Docker lab, evidence-envelope primitives,
differential validation and synthetic evaluation tools.

Work beginning at commit `b8304dd` added the first-party software, data and
infrastructure fixtures; bounded isolated repair worker; independent hidden
tests; authenticated evaluation reports; bounded Meta investigation; recorded
local Meta runs; read-only evidence dashboard; and hackathon demo materials.
The complete dated ledger is `docs/HACKATHON_BUILD_LEDGER.md`.

## Reproducible evaluation

| Measure | Verified fixture result |
| --- | --- |
| Domains completed end to end | 3: software, data processing, infrastructure configuration |
| Offline candidates evaluated | 6 |
| Complete repairs verified | 3 |
| Incomplete repairs rejected | 3 |
| False-repair acceptance rate | 0% in the six-candidate fixture evaluation |
| Authenticated evidence coverage | 6 of 6 candidates |
| Recorded offline worker time | 8,429 ms for the saved evaluation run |
| Actual Meta investigations | 9 |
| Actual Meta proposal outcomes | 4 verified, 2 rejected, 3 abstained |
| Root-cause accuracy | 9 of 9 under the disclosed case-marker rubric |
| Proposal repair success rate | 4 of 6 |
| Abstention quality | 0 of 3; uncertainty was not substantive |
| Fresh three-domain end-to-end time | 44,483 ms total |

These results cover committed first-party fixtures only. They do not establish
general autonomous repair performance or production safety.

## Safety and limitations

- Public Vercel routes are read-only; mutation and execution endpoints return
  HTTP 403.
- Workers have no production credentials or infrastructure access, network is
  disabled, and resources and output are bounded.
- Arbitrary third-party repositories remain blocked.
- HMAC proves possession of a shared runner secret, not organizational or
  public-key independence.
- Human approval is required for actions outside disposable fixtures.
- The successful Muse and System B experiments are operator-reported and must
  not be presented as third-party attestation.

## Links and release gates

- Product: `https://bravon-meta.vercel.app`
- Public sanitized source repository: `https://github.com/S-h-u-b-h-1/bravon_meta`
  (verified public; the original development history remains private).
- YouTube demo supplied by owner: `https://youtu.be/kx5_vs1fy4g`.
  Confirm playback signed out and check the uploaded video against the approved
  natural-voice animated demonstration before submitting. The earlier v3 draft
  and intermediate exports are historical.
- Current PR #11 Actions jobs are blocked before runner execution by the GitHub
  account's `$0` Actions spending budget recorded in open issue #12. The
  isolated local qualification is retained at
  `docs/evidence/local-release-2026-11-01-689a74d/`; it is not a successful
  GitHub Actions run.
- The sanitized public repository uses the owner-selected MIT license and
  privacy-preserving history export. The original private development history
  must stay private. Team/track selection, consent and portal submission remain
  owner-controlled decisions.

## Authenticated portal field map — inspected November 1

The live form exposes no separate project-name or product-URL field and no
HTML character limits. Do not submit until the owner reviews every value.

| Live field | Prepared value | Remaining gate |
| --- | --- | --- |
| Team Name | `Bravon` | Owner confirms name |
| Team Members | Shubhaang Kataruka (`shubhaang221`) | Owner confirms solo team |
| Which track are you submitting to? | Indie Developer Track | Owner selects |
| Which problem statement did you build towards? | Push the Frontier | Owner selects |
| Most Viral Track X post | Leave blank | No public post authorized |
| Project Description | Prepared below | Owner reviews |
| Public GitHub Repository | `https://github.com/S-h-u-b-h-1/bravon_meta` | Public sanitized source; owner reviews snapshot/provenance limitations |
| 3-Minute Demo Video | `https://youtu.be/kx5_vs1fy4g` | URL supplied; signed-out playback and final content review required |
| Describe your use of Meta products | Prepared below | Owner reviews |
| Why are Meta's models important? | Prepared below | Owner reviews |
| Partner technology feedback | Prepared below | Owner reviews |
| Permission to publish/share/promote submitted materials | Not accepted yet | Owner-only legal/marketing consent |

The remaining radio questions ask for personal product feedback: likelihood of
using Meta Model API, overall opinion, recommendation scores for Meta Model API
and Muse Code, biggest obstacle, comparison with other models, most important
model/tool attribute, switching friction, and likely production blocker. These
are subjective owner responses and must not be auto-selected. Evidence-grounded
notes: Muse Code was not evaluated; no partner-hosted paid inference was used;
the project values answer quality, reliable tool use, privacy, and independent
verification; model-to-model comparison was not controlled.

### Project Description

<!-- Portal copy: 173 words; 1,326 characters when whitespace is normalized. -->

**Bravon — Reliability, Proven**

Bravon is a verification-first AI engineering platform that addresses a critical weakness in AI-generated technical repairs: a plausible fix can pass visible tests while still violating the system's underlying behavioral requirements.

During the Meta Global AI Developer Hackathon, we built a bounded Meta-model investigation workflow, isolated repair verification, independent behavioral tests, false-green rejection, and evidence-backed repair reporting.

Using Meta Llama 3.1 8B, we recorded nine local investigations: four proposals independently verified, two incomplete proposals rejected, and three abstentions. A separate operator-reported Meta Muse Spark 1.3 experiment investigated a genuine DNS failure in a disposable Docker environment.

Our experimental Immortality system extends the concept by converting one verified recovery into a bounded, non-executable DNS safety invariant and testing it on a second isolated system.

Bravon's defining principle is simple: **AI proposes. Independent evidence decides.**

The pre-existing infrastructure lab and verification foundations are disclosed separately from the functionality developed during the hackathon. Our recorded experimental results are limited in scope and are not presented as general autonomous repair or third-party attestation.

### Describe your use of Meta products

Bravon used Meta Llama 3.1 8B open weights locally for nine bounded
investigations. The model received only a problem description and three
allowlisted tools: target source, public regression, and reproduced failure.
It never saw hidden tests, expected repairs, signing secrets, shell access, or
the verifier's verdict. Across the recorded runs it made 45 model requests;
four proposals passed independent verification, two plausible false-green
proposals were rejected, and three abstentions remained unverified.

A separate operator-recorded Meta Model API experiment used official Muse
Spark 1.3 for seven hosted requests on a disposable DNS failure. Muse selected
read-only diagnostics and proposed `restore_dns`; Bravon independently checked
five behaviors in a separate clone before human-approved recovery. No new API
call occurs in the submitted video, and this controller evidence is not
presented as third-party attestation or general model reliability.

### Why are Meta's models important to your solution?

Technical failures rarely arrive with a known diagnosis. Meta's model provides
the adaptive investigation layer: it chooses which bounded observation to read
next, connects evidence into a root-cause hypothesis, proposes the smallest
repair, and communicates uncertainty. Bravon's deterministic verifier provides
the independent trust layer. This separation lets the model contribute useful
reasoning without allowing model confidence, prompt wording, or a single green
test to authorize a repair.

### Partner technology feedback

No partner-hosted paid inference is part of the submitted evidence. Baseten's
OpenAI-compatible endpoint and hackathon model identifier were documented, but
no Baseten call was made because credits and spending controls were not
confirmed. The submission therefore makes no performance claim about Baseten,
Modal, or Fireworks.

## Three-minute demonstration

Show only hackathon-period work: reproduce a real fixture failure; show the
bounded Meta observation trail and untrusted structured proposal; demonstrate
an incomplete repair passing a visible test but failing an independent hidden
invariant; verify the complete repair in the isolated worker; inspect the
authenticated evidence; and close with the explicit baseline disclosure and
read-only production boundary.
