# Bravon — Verification-First Engineering Roadmap (2026-10-25)

## Product thesis
Bravon investigates technical failures, reproduces them in bounded test environments, proposes minimal changes, and independently verifies outcomes before humans approve any real-world action.

**Non-claim:** No proof that Bravon is the first product to do AI debugging or verified repair. Compete on measurable evidence quality and cross-domain adapter coverage, not "first ever" marketing.

## Current audited baseline
- FastAPI entrypoint `proofops.api:app`; Vercel hosts the simulation dashboard.
- `IncidentLab` holds state in process memory: inappropriate for persistent multi-user usage.
- DockerLab is local only, explicitly restricted to loopback, uses a separate verification stack, and requires explicit approval before applying changes.
- Model protocol enforces a read-only probe contract and validates cited evidence IDs.
- Legacy Python import names, evidence schema names, and Docker control headers stay unchanged until versioned migrations.
- Vercel deployment READY and health route working are **not** evidence of complete customer workflow readiness.
- Rebrand regression identified: `tests/test_api.py` asserted old "ProofOps" display name; updated separately.

## Release safety rules
1. Never enable unauthenticated real repair endpoints on the Internet.
2. Never permit arbitrary shell commands, arbitrary filesystem access, arbitrary destination URLs, or untrusted model-generated actions.
3. Never ship credentials or protected logs to third-party AI without express consent and minimization.
4. Each repair requires fresh observations, action allowlisting, independent verification, environment fingerprinting, human approval, and post-change checks.
5. Evidence checksums are reproducibility aids, not cryptographic attestations of truth.
6. No production deploy without passing regression and safety gates.

## Staged delivery, with acceptance checks

### 0. Stabilize current prototype
- Establish protected `main` branch; develop changes in PRs and previews.
- Run full tests with current dependencies; fix only evidenced failures.
- Check homepage, assets, /api/health, and a complete simulated inject -> diagnose -> verify -> approve -> repair -> export journey.
- Record Vercel protection behavior and independent browser access.
- Gate: pass tests + E2E + no regressions; otherwise NO-GO.

### 1. Define a portable failure/evidence protocol
- Introduce versioned domain-neutral case types: symptom, observation, reproduction recipe, hypothesis, candidate repair, verification experiment, outcome.
- Structured source identifiers, timestamps, provenance, environment snapshots, and counterevidence.
- Explicit UNVERIFIED, INSUFFICIENT_EVIDENCE, CONTRADICTED, VERIFIED states.
- Gate: test that fabricated observation IDs, stale evidence, changed environments, and partial repairs cannot be qualified.

### 2. Build secure multi-user web foundation
- Real auth, per-user authorization, persistent data, audit logs, rate limiting, isolation, idempotent operations.
- Web frontend may run on Vercel; persistent DB and privileged sandbox workers are separate.
- Model interactions operate against task-scoped capabilities only.
- Gate: cross-account access and unsafe request tests fail closed.

### 3. Ship adapter #1: code and CI failure analysis
- Accept a reproducible failing test in a controlled repository fixture.
- Collect logs/diffs/config in a read-only sandbox.
- Produce a minimal patch proposal, apply only in isolated copy, run original and regression tests independently.
- Explain results and ambiguity; never treat passing tests as complete proof.
- Gate: reproducible benchmark with hidden tests and deliberately deceptive green-test cases.

### 4. Ship adapter #2: data pipeline failures
- Controlled fixture for schema drift, null behavior, cardinality errors, timezone mismatches.
- Compare pipeline output to invariants, not just process exit code.
- Gate: detect silent data corruption that ordinary success checks miss.

### 5. Ship adapter #3: AI/ML & RAG system failures
- Controlled cases for leakage, retrieval miss, stale embeddings, citation mismatch, calibration regression.
- Independently evaluate output evidence and counterexamples.
- Gate: prove improvement in task-relevant metrics without hiding regressions.

### 6. Retain and harden existing infrastructure adapter
- Keep Docker recovery local or in authorized isolated worker.
- No general-purpose remote-command features.
- Gate: approved repairs work on disposable environments, blocked repairs remain blocked.

### 7. Publish evaluation and beta
- Establish comparators (basic rules, AI suggestion with tests only, Bravon evidence-gated).
- Track correct diagnoses, false approvals, unsafe proposals, time-to-reproduce, reproducibility, evidence coverage, and compute costs.
- Adversarial cases include noisy logs, fabricated citations, stale snapshots, partial fixes, and prompt injection.
- Publish precise limitations; claim novelty only on demonstrated, reviewed findings.
- External beta only after access-control and safety acceptance.

## First research challenge
**False-green repair challenge:** construct cases where an apparent fix passes a narrow test but violates an independent behavioral invariant. Demonstrate whether the evidence gate abstains or rejects it. This is a testable differentiation, not a guaranteed novel invention.

## Immediate next engineering tasks
1. Run/observe existing test suite at repository head (not yet verified by connected GitHub tooling).
2. Examine UI API mutation routes for safety under serverless concurrency; do not publish them unauthenticated.
3. Draft domain-neutral protocol specification with backward-compatible adapters.
4. Add a falsifiable false-green fixture and a strict independent oracle.
5. Keep production release gated throughout.
