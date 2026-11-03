# Bravon False-Green Benchmark v1

## Purpose
Measure whether a verifier rejects repairs whose narrow original tests pass but independent behavioral invariants are contradicted, and whether it abstains on missing evidence.

## Fixture definitions
The benchmark has five hand-authored cases: genuine repair, violated boundary rule, violated accounting rule, originally failing test, and missing verification evidence.

The intentionally weak comparator checks **only** `original=True`. It is not a representative modern coding agent.

## Expected fixture results
- Weak green-test-only baseline: 2/5 correct verdicts, three false approvals.
- Bravon invariant verifier: 5/5 correct verdicts, zero false approvals.
- These are expected outputs asserted by CI, **not independent field performance measurements**.

## Trust assumptions and release limitations
- `trusted_sources` is a local allowlist; a caller providing fake observations can still fool the pure verifier.
- The separately signed evidence envelope protects integrity only for keys controlled by the verifier's trusted execution infrastructure.
- HMAC authentication does not prove measurement truth or runner isolation.
- In-memory replay state is not safe across serverless instances; use a durable transaction/unique constraint before deployment.
- Stale or unrelated invariants cannot establish repair correctness even when all pass.
- A truly independent evaluation needs hidden fixtures, source-grounded counterexamples, separate runner identity, and scoped repair execution.

## Required next gates
1. Validate on real failing repositories with frozen reproductions and hidden regression tests.
2. Demonstrate tampered evidence, replay, bad provenance, stale environment, and partial fix are rejected.
3. Establish durable atomic replay storage and secure runner identities.
4. Compare to credible coding-agent and testing baselines with disclosed costs.
5. Do not deploy the verifier or publish a generalizable accuracy claim until those gates pass.
