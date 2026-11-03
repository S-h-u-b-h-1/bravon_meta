# Bravon publication security audit

Audit refreshed: November 1, 2026 (IST). Scope: all tracked files and history
reachable through source-candidate commit
`edfaae251297ec50246687756e5df7103b2c4ca1`, the hackathon delta from peeled
cutoff commit `b0dd80f721d28d36e9e680bb18181ae20d4d0347`, and the local replacement
video review artifact.

The annotated cutoff tag object is
`28bba5ded9a53d61a75ab430d40ae9a964c86aa3`; dereferencing the tag with `^{}`
produces the documented cutoff commit. The baseline has not moved.

## Automated results

- Gitleaks 8.30.1 scanned the complete pre-publication history. Result:
  zero unsuppressed findings.
- The final rescan at source candidate `edfaae2` again found zero history
  leaks. Directory mode reported only the already reviewed response-shape prose
  in `docs/NEMOTRON_FORMAT_HOTFIX_V083.md`; it contains no credential.
- An unpublished `git archive` from exact source candidate `edfaae2` contains
  276 tracked files and has SHA-256
  `e6e01043af577a3b60c9fbe775b495332070a201bcdaca3dff5be943230c9f3a`.
  Targeted scans found zero owner home paths, Gmail addresses, populated model
  or API-key assignments, and private-key PEM blocks. Machine evidence is in
  `docs/evidence/publication-archive-2026-11-01-edfaae2.json`.
- One exact Gitleaks fingerprint is suppressed in `.gitleaksignore`. Manual
  review confirmed it is prose describing model response fields in
  `docs/NEMOTRON_FORMAT_HOTFIX_V083.md`, not a key or token.
- `pip-audit` 2.10.0 found zero known vulnerabilities across 58 packages in a
  fresh Python 3.12 environment installed from `.[dev]`. The unpublished local
  `bravon` package itself was the only skipped item.
- Bandit 1.9.4 reported zero high- or medium-severity findings across the
  Python source at that candidate.
- The exact-source local qualification at commit
  `689a74dda31762850d00f122d5e7d66f179877b3` passed 464 non-Docker Python
  tests with 2 skips, 50 Node tests, Chromium and WebKit smoke, 42 axe
  route/viewport checks, security thresholds, replay verification and
  `git diff --check`. The complete Docker-backed suite remains unrun because
  the pinned worker image is unavailable, and GitHub Actions remains blocked
  before runner steps by issue #12. This audit does not represent those gates
  as green.
- After the later model-evidence UI changes, exact-source delta qualification
  at `df164ef0cdaa7da047b2717a0fc2b9e9531200d9` repeated the complete Python
  collection, non-Docker subset, Node suite, both browser engines, axe matrix,
  dependency audits, Bandit and Gitleaks. The results remained unchanged.
- The final November 1 `git archive` dry run produced 251 tracked files totaling
  4,964,352 bytes. It contained no video, private Muse/Immortality receipt,
  private key or populated credential file. The only generic `.env*` match was
  the intentional `.env.example`, whose API-key value is blank.
- Two targeted credential-assignment matches were deliberate rejection/privacy
  test canaries. A directory-mode Gitleaks scan repeated the already reviewed
  `docs/NEMOTRON_FORMAT_HOTFIX_V083.md` response-shape false positive because
  the temporary export path changes its fingerprint; no new finding appeared.
- The current offline release gate passed with 68 Python files parsed, 50
  frontend behavior tests, 83 Python contract/privacy tests, disabled remote
  execution, clean patch format and loopback HTTP smoke. It initiated zero
  model requests and zero Docker commands.

## Manual trust-boundary review

- Public Vercel routes cannot start Docker, invoke model inference, mutate
  incidents, or apply repairs. Mutation attempts return HTTP 403.
- The verifier accepts only one exact fixture target filename and a bounded
  complete replacement. It has no shell command, URL, package installation, or
  arbitrary repository input.
- Docker execution uses an absolute resolved CLI path, a digest-pinned image,
  no network, read-only root, non-root UID, dropped capabilities,
  no-new-privileges, and CPU, memory, PID, time, output, and patch-size limits.
- The model receives the target, public regression, and reproduced failure
  through three allowlisted read-only tools. Hidden behavior tests and signing
  keys are excluded.
- Evidence JSON contains no user home path, email address, external hostname,
  account identifier, API key, authorization header, private key, password, or
  stored prompt body.
- The first evidence export review found absolute local paths retained by
  pytest in two JUnit skipped-test messages and raw match text retained by a
  Gitleaks report. Commits `1415be6` and `3da2be1` replaced those values with a
  repository placeholder and a minimized classification record. The final
  archive has zero matches for the owner's local path, hostname, or email.
- Evidence signatures are HMAC authentication records, not public-key
  attestation or proof of organizational independence.
- The revised 99.518-second v3 candidate was checked at all eight narration
  midpoints. OCR, MP4 strings and metadata exposed no user path, email,
  credential, authorization token, private report filename or account
  identifier. Visible provenance language explicitly labels recorded evidence,
  operator control and the absence of third-party attestation.

## Publication disclosures and remaining owner decisions

- Git commit metadata contains both a GitHub noreply address and a Gmail author
  address. Current history contains 50 Gmail-domain author records and 261
  GitHub-noreply author records. Making the repository public will expose the existing
  Gmail address.
- **Option A — accept the exposure:** preserve commit hashes, tags, review links
  and the strongest hackathon timeline evidence. This is the least disruptive
  option but requires explicit owner acceptance.
- **Option B — rewrite historical identities:** replace author/committer email
  metadata, recreate tags and force-push every affected reference. This changes
  commit hashes and can invalidate PR links, signed references and evidence
  manifests. It requires a separate backup, publication audit and explicit
  destructive-history authorization.
- **Option C — publish a sanitized export:** create a new public repository with
  reviewed files and an explicit provenance manifest. This avoids exposing the
  private history but weakens independently inspectable build chronology and
  must first be confirmed acceptable under the live submission rules.
- `.mailmap` and GitHub's future-email privacy setting do not remove raw email
  metadata from existing commit objects.
- Direct dependency and model attribution is recorded in
  `THIRD_PARTY_NOTICES.md`. The owner-selected MIT license is in `LICENSE`.
- Repository visibility, the final video, competition track and team list, and
  final submission remain owner-controlled actions.
