# Bravon pre-hackathon baseline

This records functionality present before the Meta Global AI Developer
Hackathon begins on October 26, 2026.

- Frozen feature snapshot: `5082769ed47374ce5c3524247d2ff9aaf12428fe`
- Commit time: October 25, 2026 at 7:02:56 PM IST
- Immutable feature-snapshot tag: `pre-hackathon-2026-10-26`
- Final pre-build cutoff tag: `hackathon-start-baseline-2026-10-26`
- Annotated tag object: `28bba5ded9a53d61a75ab430d40ae9a964c86aa3`
- Peeled final-cutoff commit: `b0dd80f721d28d36e9e680bb18181ae20d4d0347`
- Branch at freeze: `main`
- Feature-snapshot validation: 303 tests passed locally on October 25, 2026
- Final-cutoff validation: 304 tests passed locally on October 25, 2026

The feature-snapshot tag points to the original code baseline. This document
was intentionally committed after that tag so it cannot be mistaken for
product functionality present at the earlier snapshot.

## Pre-kickoff maintenance after the feature snapshot

The final cutoff tag also contains the following October 25 work. These changes
are pre-existing maintenance and preparation, not hackathon-built product
capability:

- `7b07d0b`: this baseline and the official-rules eligibility gate;
- `76e375b`: CI trigger correction for the production `main` branch;
- `bb32f04`: architecture and submission-document scaffolding;
- `08a438e`: pinned current GitHub Actions and Ubuntu runner versions;
- `b264887`: worker-isolation and fixture-provenance security requirements;
- `fa9a4fc`: blocked unauthenticated hosted Meta inference so future event
  credits cannot be spent from the public simulation endpoint.

The last item is a safety restriction on an existing optional Meta client. It
does not add model capability, a new adapter, a worker, a fixture, or evaluation
evidence. All code and documents reachable from the final cutoff tag must be
treated as pre-existing in the submission disclosure.

## Existing product and evaluation capabilities

- FastAPI dashboard for deterministic simulated incidents.
- Closed repair allowlist, cloned-state verification, explicit approval, and
  rollback-oriented state transitions.
- Opt-in disposable Docker Compose lab for CoreDNS, Nginx, backend, and probe
  faults. Hosted Docker and remote repair paths are disabled by default.
- Read-only investigation protocol with bounded tools, evidence identifiers,
  cited proposals, and fail-closed parsing.
- Optional pre-event Meta Muse advisory client for synthetic incident analysis.
  It had mocked tests but no verified live Meta inference in the authoring
  environment.
- Optional local Meta Llama through Ollama and optional free OpenRouter
  Nemotron investigation paths. Both require explicit operator selection; the
  cloud path requires explicit data-transfer confirmation.
- Seeded synthetic benchmarks, blind-label evaluation, replay verification,
  model protocol trials, and disposable-Docker qualification tooling.
- False-green repair verifier with independent invariants, executable refund
  fixture, differential before/after records, immutable execution manifests,
  HMAC evidence envelopes, timestamp and key binding, and atomic durable SQLite
  nonce replay protection.
- GitHub Actions tests on Python 3.10, 3.12, and 3.13 and Vercel preview
  deployments.

## Evidence already available

- Rule-based simulated benchmarks and 42-case seeded synthetic evaluations.
- Mocked Docker controller and safety tests.
- Prior documented local Docker qualification for known fault families, with
  limitations recorded in the repository.
- Hand-authored false-green fixtures demonstrating why narrow green tests are
  insufficient.

These results do not establish general model reasoning, unseen-bug repair,
runner independence, or production infrastructure safety.

## Not present at the freeze

- No hackathon-period Meta model run or accepted participant credential.
- No end-to-end cross-domain demonstration using the event's Meta tooling.
- No safely isolated general-purpose worker for untrusted repository code.
- No real external software-bug corpus with hidden independent regression
  tests.
- No database, CI/CD, infrastructure, or AI/ML failure adapters integrated into
  one common demonstration contract.
- No dashboard view for signed execution manifests or provenance verdicts.
- No production-grade multi-host replay database or hardware/workload
  attestation.
- No final hackathon submission form, demo video, evaluation report, or entry.

## Hackathon delta policy

All submission claims must distinguish this baseline from work created after
the event starts. New reports should record commit IDs, model and API identity,
test fixtures, execution environment, evidence digests, and verifier results.
Pre-existing Bravon components may support the entry, but the judged
Meta-powered capability and its evaluation must be independently visible.
