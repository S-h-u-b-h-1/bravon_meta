# ProofOps v0.9 provenance preservation hotfix

## Why

The v0.9 dashboard had local rule/probe buttons able to replace a previously qualified hosted-model diagnosis. The recovery JSON export did not include the model transcript, evidence gate or source.

## What changes

- Once a hosted-model investigation has an independently accepted **repair** proposal, re-analysis is disallowed for that incident, both through CLI/API and dashboard controls. Use verify, human-approved repair, or reset.
- After **qualified hosted-AI** sandbox verification succeeds, re-analysis is also refused. The existing rule-based re-analysis behavior is unchanged.
- When the model abstains or the gate **rejects** it, the operator can still use deterministic rules as a fallback; that fallback must be clearly labeled as rules, not model inference.
- Exported recovery JSON includes the original investigation transcript, raw action, evidence gate, and verification and recovery proof. It may contain generated private subnet addresses: do not upload this JSON publicly without review.
- The recovery proof checksum now includes the diagnostic source, raw action, gate verdict and a SHA-256 digest of the stored investigation, so it is linked to the recorded AI decision. This is an integrity checksum, **not** a cryptographic signature or independent attestation.
- Recovery history keeps the source label and raw action, though full historic traces require exporting the report **before** starting the next incident.

No extra API requests, no paid models, no production service access, no change to the action allowlist. The package version remains 0.9.0.
