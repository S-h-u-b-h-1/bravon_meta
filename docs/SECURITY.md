# Security boundaries — v0.1

This repository is a **single-user local demonstration**, not a secured multi-user product. Only serve it on `127.0.0.1`; the repair endpoints intentionally have no authentication and should not be placed on a public network.

- The three catalogued actions alter an in-memory `LabConfig`. They do not run shell commands or edit DNS, Nginx, Docker, GitHub, or OS files.
- Model inference is *opt-in*, disabled unless an API key is configured and an operator selects Meta analysis in the UI. Only explicitly simulated topology and probe data is sent. Avoid replacing that telemetry with private or protected customer data without additional controls and authorization.
- Model-produced text is treated as untrusted; proposed action must equal the independently derived action. Cited evidence IDs must point to measured failures. No model output can specify a new action handler.
- Before writing simulated state, a separate cloned-state verification must have passed. The live revision and fingerprint must still match. The operator must approve. Independent probes run again after apply, with rollback on failure.
- The SHA256 digest in verification is an **integrity checksum for reproducibility**, not an independent signature, tamper-resistant audit log, externally notarized fact, or proof of real infrastructure recovery.
- No persistence; all incident history and approvals disappear on server restart. There is no secrets vault, RBAC, rate limiting, structured log redaction, isolation across users, or protection from local browser request forgery yet.
- The next milestone must add authentication, authorization, anti-CSRF protection, persistent evidence records, network-level sandbox isolation and redaction BEFORE any public or connected deployment.

## Hackathon execution boundary

The public Vercel application is a dashboard and evidence viewer. It must not accept source archives, execute repairs, run arbitrary commands, or hold worker credentials. Hackathon demonstrations that execute code must use committed fixtures in a disposable local or CI worker.

Treat the fixture, model response, candidate patch, process output, file paths, and generated report as untrusted. The worker must fail closed unless all of these controls are active:

- an allowlisted fixture ID selects fixed commands without a shell;
- the environment is scrubbed of credentials and outbound networking is disabled;
- CPU time, wall time, process count, output size, and writable storage are bounded;
- writes stay inside a fresh temporary copy; absolute paths, traversal, symlinks escaping the copy, binary changes, and edits outside the fixture allowlist are rejected;
- baseline reproduction and candidate verification run in separate fresh copies;
- hidden regression tests are withheld from the model and executed by the independent verifier;
- temporary state is removed after the run; the manifest is signed outside the worker only after outputs and environment metadata are collected.

These controls constrain a demonstration worker; they do not make hostile multi-tenant code execution safe. A hosted execution service remains out of scope until it has stronger isolation, authentication, authorization, monitoring, and abuse controls.

## Fixture and evidence provenance

Every hackathon case must have a checked-in provenance record containing:

- stable case ID and domain;
- whether the fixture is original or derived, with source URL, author, and license when derived;
- collection or creation date, including whether it predates the October 26, 2026 build window;
- hashes for the frozen failing input, public tests, and independent hidden tests;
- permitted files and commands, expected failing behavior, and the invariant used to judge a repair;
- disclosure of any pre-existing Bravon capability reused by the case.

Do not import customer repositories, private incident logs, personal data, proprietary benchmarks, or code whose license does not permit the planned use. Reports must identify simulated evidence and model-authored claims, retain counterevidence, and never present a checksum or signature as proof that the underlying observation is true.
