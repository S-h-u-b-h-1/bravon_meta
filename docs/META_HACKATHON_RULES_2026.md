# Meta Global AI Developer Hackathon rules review

Reviewed on October 25, 2026 from Meta's event page and the linked Cerebral
Valley Event Waiver titled “Hackathon Terms & Conditions (“Official Rules”) and
Event Waiver.” The event page still said the rules would be published before
October 26, but the linked waiver already contained them.

Official sources:

- https://dev.meta.ai/events/global-hackathon
- https://cerebralvalley.ai/e/meta-ai-developer-hackathon
- https://cerebralvalley.ai/e/meta-ai-developer-hackathon/waiver
- https://cerebralvalley.ai/e/meta-ai-developer-hackathon/hackathon/submit

## Eligibility gate

Participation requires a truthful application submitted by October 25 at
11:59 PM ET, selection among at most 20,000 participants, and acceptance of the
Official Rules. Participants must be at least 18 and the age of majority where
they live. Geographic, sanctions, employment, government-affiliation,
household, and immediate-family exclusions apply as written in the Rules.

The repository cannot establish the participant's personal eligibility,
selection, or acceptance. Those remain participant-controlled gates.

## Pre-existing code

The Rules reviewed on October 25 do not expressly require every line to be
created during the event and do not expressly prohibit pre-existing code.
They require the submission to be the participant's or team's original work,
solely owned by them, and free of third-party rights violations. Contracted
technical help is allowed only when submitted components remain the
participant's own work and rights are owned. Open-source software or hardware
is allowed when its licenses are followed and the submission enhances or
builds on it.

Decision: Bravon is conditionally usable. Preserve and disclose its pre-event
baseline, comply with every dependency license, and make the judged Meta-powered
contribution traceable to the hackathon period. This is an evidence-based rules
interpretation, not legal advice.

## Required Meta technology

The Rules say participants build with Meta AI products, including named Meta
models and other products identified on the event page. The event page lists
the Muse Spark series, Muse Wonder, Muse Image, SAM 3.1, Meta open-weight
models, and Muse Code. “Use of Meta AI Tooling” is 25% of project judging and
specifically rewards creative use beyond a basic integration.

Bravon's qualifying path is Meta-model-assisted technical investigation. The
model may choose bounded read-only probes, form a diagnosis, and propose a
repair. Independent code must reproduce the failure and verify behavior; the
model must never authorize or directly execute a real repair.

Selected participants are offered $150 of Meta Model API credits for the
ten-day window, subject to separate credit terms. No credit or paid service may
be used by this repository without the participant controlling the credential
and accepting its terms. Bravon must retain a zero-cost offline path.

## Tracks and teams

Each participant and submission enters one track only.

- Indie Developer: individuals, students, or teams of at most four.
- Startup: technical founders; the representative must be an active employee.

A team must appoint one eligible, authorized representative. That person
submits the project, identifies every member, receives notices and any prize,
and confirms every member accepted the Rules.

## Intellectual property and confidentiality

Entrants retain ownership of their submission. Submission grants the
Organizers a perpetual, irrevocable, worldwide, royalty-free, non-exclusive
license broad enough to use, adapt, publish, distribute, display, demonstrate,
and create derivative works from it.

Materials shared during the event are not confidential. The Rules grant the
Organizers an additional broad, perpetual license over materials provided or
used in connection with the event. Do not include secrets, private customer
data, proprietary third-party material, or infrastructure identifiers in the
submission or demo.

## Judging

- Impact: 30%
- Use of Meta AI Tooling: 25%
- Technical Depth and Execution: 20%
- Demo: 25%

The demo criterion covers a working live demonstration and video quality.
Bravon's evaluation must therefore show a genuine failing behavior, bounded
Meta-assisted investigation, a proposed repair, independent regression checks,
and an evidence-backed verdict in one repeatable flow.

## Submission requirements and dates

Projects are submitted through the official Cerebral Valley portal. The
published deadline is November 4, 2026 at 9:00 PM ET. Judging is November 4–8,
with the closing ceremony listed for November 9. Dates may change at Meta's
discretion, so the official page remains authoritative.

As of October 25, the submission URL redirected to the public event page, so
its exact fields were not yet visible. Known requirements are one track, the
team representative and member identities when applicable, a working project,
and a high-quality demo video. Recheck the form after participant acceptance
and before drafting final materials.

## Go/no-go controls

Do not represent Bravon as an eligible entry unless the participant confirms
selection and acceptance. Do not begin paid inference, submit the project, or
accept credits automatically. Keep production repair execution disabled and
require human approval for any real infrastructure change.

## Live Participant Guide confirmation — October 27, 2026

The live Cerebral Valley Participant Guide was rechecked at:

- https://cerebralvalley.ai/e/meta-ai-developer-hackathon/details

It resolves the remaining model-eligibility question. Stage One accepts a
project that reasonably used the Meta Model API **and/or Meta's open-weight
models** during the hackathon. Bravon's recorded local Meta Llama 3.1 8B runs
therefore satisfy the guide's baseline Meta-model requirement without a paid
API call. Muse Glimmer or Muse Spark Open is required only for the separate
“Best Build on Meta Open Weight Models” bonus prize.

The guide also confirms:

- repositories must be public at submission;
- the demo may highlight only functionality built during the hackathon;
- startups may build on existing products only with clear new-work disclosure;
- a three-minute demo video and publicly accessible repository are required;
- the deadline is November 4, 2026 at 9:00 PM EST, which is November 5 at
  7:30 AM IST;
- judging weights are Impact 30%, Meta AI Tooling 25%, Technical Depth and
  Execution 20%, and Demo 25%.

Those weights contradict the earlier equal-weight assumption. The live guide
is authoritative for the submission plan.

### November 1 live guide recheck

The authenticated Participant Guide still states:

- repositories must be public at submission;
- the demo may show only features, code, and functionality built during the
  hackathon, with pre-existing startup foundations clearly disclosed;
- Stage One accepts reasonable use of the Meta Model API and/or Meta
  open-weight models;
- submissions require a publicly accessible repository and three-minute demo
  video by November 4 at 9:00 PM EST;
- judging uses Impact 30%, Meta AI Tooling 25%, Technical Depth and Execution
  20%, and Demo 25%; and
- Baseten-hosted Muse Spark Open must use
  `meta-models/muse-spark-open-1026` for this event.

This directly contradicts the previously supplied equal-weight summary. The
live Participant Guide and Official Rules agree on 30/25/20/25, so submission
materials use those weights.


## October 31 release compliance checkpoint — PR #11

Official public event sources checked:
- https://dev.meta.ai/events/global-hackathon
- https://events.cerebralvalley.ai/e/meta-ai-developer-hackathon
- https://cerebralvalley.ai/e/meta-ai-developer-hackathon/waiver

**Confirmed publicly:** Indie Developer track; Push the Frontier theme; Meta
Model API and Meta open-weight model use; submission on November 4, 2026 at
9:00 PM Eastern Time (November 5, 7:30 AM IST, after US daylight-saving time
ends); and judging weights of Impact 30%, Meta AI Tooling 25%, Technical Depth
and Execution 20%, and Demo 25%. The event organizer may change posted dates.

**Not established from the public pages:** acceptance/eligibility of the
repository owner, exact authenticated submission fields, and whether the
participant has formally accepted the rules. Recheck the authenticated portal
before release; do not infer those facts from a working submission URL.

### Hackathon-specific release gates

- [x] **Work provenance:** demo/video claims were compared with
  `docs/HACKATHON_BUILD_LEDGER.md` and the pre-kickoff baseline
  `b0dd80f721d28d36e9e680bb18181ae20d4d0347`. Attribute inherited
  simulation/Docker foundations as pre-existing; demonstrate only newly
  built components as hackathon features.
- [x] **Meta evidence:** submission and video materials separately identify local Llama 3.1 investigations
  versus operator-reported official Muse Spark 1.3. Never label deterministic
  browser simulation, remote controller or saved fixtures as live Muse calls.
  No new paid or credential-bearing request without owner authorization.
- [x] **Truthful outcomes:** submission copy keeps verified, rejected false-green, abstained,
  synthetic, self-digested controller record and independently attested
  results as distinct categories. Do not assert generic immunity or a
  statistically measured repair rate beyond the published fixtures.
- [ ] **Demo:** finish and owner-review a new maximum-three-minute video
  featuring hackathon-built capability, the genuine Meta investigation
  boundary, visible failure and independent verdict; verify working playback
  and public accessibility before submission.
- [ ] **Working site:** validate the complete jury journey on desktop, tablet
  and mobile, plus keyboard and screen-reader checks. Browser smoke does not
  equal WCAG certification. Test failures visibly fail closed.
- [x] **Source, IP and privacy:** dependencies, asset
  licenses, code history, commit email metadata, embedded credentials and
  downloadable artifacts were independently reviewed. The remaining historical
  commit-email disclosure is an explicit owner decision. Do not publish private
  operator reports, addresses, API keys or Docker logs.
- [ ] **Release engineering:** pass the full supported test matrix and
  browser checks on the exact commit. Resolve GitHub Actions issue #12; an
  independently passing snapshot does not replace CI.
- [ ] **Real Docker:** review pinned linux/amd64 image SBOM/CVEs, restore
  trusted CI, and obtain separate owner consent for one bounded cloud run.
  Do not enable the runner from a PR, browser page or public API.
- [ ] **Submission gate:** confirm participant selection/rules acceptance,
  repository public-readiness, video URL, project links, and form fields
  in the authenticated Cerebral Valley portal. Public repository status
  and final submission require explicit owner approval.

**Decision:** release NO-GO until all relevant gates have execution evidence.
Draft PR #10 and PR #11 remain unmerged; production and remote execution
are unchanged. This checklist does not itself prove any gate has passed.
