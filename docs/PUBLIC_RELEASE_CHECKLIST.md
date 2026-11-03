# Public repository and submission checklist

Do not change repository visibility or submit the project until every required
item is checked and the owner explicitly authorizes the external action.

## Code and history

- [x] Frozen pre-kickoff tag and exact commit recorded.
- [x] Hackathon-period commits and capabilities recorded separately.
- [x] Current tracked files contain no `.env`, private key, certificate, or
  common API, GitHub, or AWS secret pattern in the targeted scan.
- [x] Git history contains no match for the same targeted secret patterns.
- [x] Gitleaks 8.30.1 scanned the complete history with zero unsuppressed
  findings.
- [x] Review every tracked evidence file for personal paths, hostnames, account
  identifiers, proprietary data, and accidental prompts.
- [x] Dependency, asset, runtime, and model attribution recorded in
  `THIRD_PARTY_NOTICES.md`.
- [x] Owner-selected MIT project license added after direct dependency and
  bundled-asset compatibility review.
- [ ] Owner accepts that existing Git history exposes a Gmail author address.

## Security behavior

- [x] Public investigation and repair mutation endpoints return HTTP 403.
- [x] Docker, model credentials, and runner signing keys remain local.
- [x] Security headers deny framing and object embedding, disable camera,
  microphone, and geolocation, and restrict scripts and connections to the
  same origin.
- [x] Worker image is digest-pinned and CI pulls the exact digest.
- [x] Worker has no network, a read-only root, non-root UID, dropped
  capabilities, no-new-privileges, and bounded resources.
- [x] Security review of the current public diff and Git history recorded in
  `docs/PUBLICATION_SECURITY_AUDIT.md`.

## Product and evidence

- [x] Desktop verified-repair journey browser-tested.
- [x] Abstention journey browser-tested without a misleading success state.
- [x] Mobile layout and workflow navigation visually tested.
- [x] Automated accessibility scan covered all seven routes at mobile, tablet,
  and desktop sizes with zero WCAG 2/2.1 A/AA and WCAG 2.2 AA violations.
  This is not a manual assistive-technology certification.
- [x] WebKit smoke covered the same 21 route/viewport combinations with HTTP
  success, no page errors and no horizontal overflow. This is not manual
  Safari or assistive-technology certification.
- [x] Production health, run-list API, and public write denial verified.
- [x] PR #10 previously passed all three supported Python versions.
- [ ] Current PR #11 CI is admitted and green. GitHub refuses to start jobs
  because the account has a `$0` Actions spending budget and the owner cannot
  add a payment method or increase it. Issue #12 remains open as an external
  infrastructure blocker. Local evidence is not a successful Actions run.
- [x] Commit `689a74dda31762850d00f122d5e7d66f179877b3` completed the
  isolated local non-Docker release suite. Machine-readable reports, versions,
  raw logs and hashes are in
  `docs/evidence/local-release-2026-11-01-689a74d/`.
- [x] Authenticated participant portal opened on November 1 and every live
  submission field was reconciled with `docs/HACKATHON_SUBMISSION_DRAFT.md`.
  The form was not filled or submitted; subjective responses, consent, public
  repository URL and video URL remain owner-controlled.
- [x] Historical local 162.32-second demo draft recorded and mechanically
  reviewed; hash and media properties are in `docs/HACKATHON_VIDEO_DRAFT.md`.
  It predates the Immortality evidence and is not the final submission video.
- [x] Replacement 99.518-second local demo draft recorded and mechanically
  inspected with 1080p video, narration, captions and reviewed contact sheet.
  A November 1 v3 pass replaced tiny full-page evidence with readable close-ups
  and added explicit recorded-versus-live labels. It remains an unapproved
  local review artifact.
- [ ] Owner listens to and approves or replaces the generated narration.
- [ ] Upload the approved three-minute video.
- [ ] Verify the video and repository links from a signed-out browser.

## Owner-controlled actions

- [ ] Confirm competition track and team list.
- [x] Live Participant Guide permits Meta open-weight models in Stage One;
  actual local Meta Llama 3.1 evidence satisfies that stated baseline.
- [ ] Decide whether to pursue the separate Muse Glimmer/Muse Spark Open bonus;
  do not activate billing or paid inference without authorization.
- [ ] Explicitly authorize making `S-h-u-b-h-1/bravon` public.
- [ ] Explicitly authorize the final submission.
