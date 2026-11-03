# Bravon hackathon architecture

Prepared before kickoff as permitted architecture and case planning. Product
implementation and event-period evaluation must be recorded separately from
the immutable `pre-hackathon-2026-10-26` tag.

## Demonstration claim

Bravon investigates a reproducible technical failure with a Meta model,
proposes a bounded repair, executes only inside a disposable offline worker,
and accepts the repair only when independent behavioral tests pass against the
same frozen case.

```text
frozen failing case
  -> allowlisted read-only probes
  -> Meta Model API investigation
  -> bounded patch proposal
  -> disposable offline worker
  -> before/after regression tests
  -> signed execution manifest
  -> independent Bravon verdict and report
```

The AI never supplies the final correctness verdict. The verifier does not see
the model's confidence when deciding whether evidence proves the repair.

## Reused baseline

- `proofops.model_protocol`: bounded tool loop and fail-closed JSON parsing.
- `proofops.frontier_eval`: Meta Responses API and function-calling adapter.
- `bravon_verification`: domain-neutral independent invariants.
- `bravon_execution_contract`: immutable two-revision execution records.
- `bravon_signed_execution` and `bravon_provenance`: authenticated manifests,
  key identity, freshness, and replay protection.
- Existing Docker and dashboard components remain opt-in demonstrations.

These are disclosed pre-event foundations. The cross-domain case contract,
worker, Meta investigation prompts, event evaluation, evidence report, and
dashboard experience are the intended hackathon-period delta.

## Meta integration

Primary model: Muse Spark through Meta Model API's Responses protocol. It has
the required tool-calling and structured-output surface and minimizes credit
use. Muse Wonder may be evaluated only if event credits are active and Spark
cannot complete a documented case. A locally available Meta open-weight model
is the zero-network fallback.

The model receives only:

- case-neutral problem text;
- a read-only probe catalog;
- bounded probe results with evidence IDs;
- the allowed repair surface and patch schema.

The model never receives hidden regression tests, expected actions, signing
keys, host credentials, environment variables, or production data.

Live requests require an explicit command flag, a privately supplied key, and
an event-credit budget. Dry-run and scripted-provider modes remain the default.

## Cross-domain case contract

Each committed case will contain:

- a stable case ID and domain;
- a minimal source fixture with one reproducible defect;
- an exact failing reproduction command;
- public diagnostic probes that do not reveal the fix;
- hidden independent behavioral tests;
- a clean environment fingerprint;
- strict time, output, file, and network limits;
- expected evidence fields, not an expected AI answer;
- a license and provenance record.

Initial case matrix:

| Domain | Genuine failure | Independent proof |
| --- | --- | --- |
| Software | Refund logic passes a narrow happy-path test but mishandles invalid quantity | Boundary and accounting invariants |
| Database | SQLite write path permits a duplicate idempotency key under retry | Unique-state and no-double-effect tests |
| CI/CD | Deployment gate treats a textual false result as success | Failed-check blocks deploy; true result permits it |
| AI/ML | Label-index drift silently swaps two classifier outputs | Fixed hidden examples and mapping invariants |
| Infrastructure | Disposable DNS, proxy, or backend fault | Existing isolated customer-path and component probes |

The first four run offline with the standard library. The infrastructure case
requires explicit local Docker opt-in and is not required for hosted operation.

## Worker boundary

The hosted Vercel app must never execute submitted code. The event worker is a
local or CI process restricted to committed Bravon fixtures.

Required controls:

- copy a known fixture into a fresh temporary directory;
- remove inherited secrets and proxy credentials;
- disable network access;
- allow only declared executable and argument arrays, never a shell string;
- enforce wall-clock, process, output, file-count, and byte limits;
- reject symlinks, absolute paths, traversal, binary patches, and undeclared
  file changes;
- execute failing revision and candidate revision as distinct runs;
- clean the workspace after every result;
- sign the manifest outside the worker with a runner-specific key;
- fail closed on timeout, cleanup failure, missing evidence, or signature error.

Container isolation is preferred for the final demo. A local subprocess mode
may exist only for committed fixtures and must state that it is weaker than a
container boundary.

## Repair proposal boundary

The model may return a small unified diff limited to declared text files. The
controller validates paths and size before applying it inside the disposable
copy. It never applies a model patch to the repository checkout, host, Docker
daemon, database, Vercel project, or external infrastructure.

Human approval remains mandatory before any real-system change. The hackathon
demo proves repair behavior only inside its frozen fixture.

## Evaluation

Every case must run through four comparisons:

1. failing revision with public reproduction;
2. model proposal in a fresh worker;
3. candidate revision with hidden regression tests;
4. a misleading green-only baseline to measure false-green rejection.

Report model, API/provider, prompts digest, probe transcript, patch digest,
before/after commit digests, image/runtime digest, test IDs, timings, token use,
estimated credit use, verifier verdict, and all failed attempts. No cherry
picked reruns may replace earlier failures.

Minimum demo acceptance:

- at least three domains execute end to end;
- at least one valid repair and one rejected partial repair;
- no network or host mutation by the worker;
- replayed or tampered evidence is rejected;
- the same report verifies independently after generation;
- the dashboard accurately distinguishes model claims from proven behavior.

## Build order after kickoff

1. Implement fixture schema and offline worker with one software case.
2. Add hidden regression verification and signed report generation.
3. Adapt the existing Meta tool loop to the domain-neutral case protocol.
4. Add database, CI/CD, and AI/ML cases.
5. Integrate read-only reports into the dashboard.
6. Run deterministic and live-credit evaluations without deleting failures.
7. Record the demo and finalize submission materials.

Do not start live Meta evaluation until participant selection, Rules acceptance,
credential setup, and event-credit terms are confirmed.
