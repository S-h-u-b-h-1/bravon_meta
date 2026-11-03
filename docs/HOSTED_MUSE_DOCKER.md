# Bravon — Hosted Muse investigator for the disposable Docker lab

**Status (2026-10-28):** Offline test suite and official Meta live single-incident
Docker recovery exercise passed. The integration remains **Terminal-only and
explicitly opt-in**; one recovered disposable DNS fault is **not** broad model
reliability or production-readiness qualification. Baseten integration has not
been validated with a Baseten-issued credential.

## Architecture

1. Existing DockerLab `inject` creates a fault in the known disposable CoreDNS,
   Nginx and backend Compose services (no published host ports).
2. The CLI-only `--investigator hosted-muse` option creates a model-backed
   `WireInvestigator` with fixed read-only tools. No arbitrary commands, files,
   URLs or model-produced Python are executable.
3. The selected hosted model chooses an allowlisted probe or an explicitly
   represented final action. Candidate repair actions are offered only after
   generic, action-specific prerequisite observation IDs have been collected;
   abstention is always allowed. The model still chooses its own action and
   citations. No raw decision is overwritten or citations silently inserted.
4. Bravon's existing `assess_proposal` rejects unsupported/contradictory
   recommendations. A qualified diagnosis is locked against rule-based
   replacement. `verify` separately reproduces and tests the repair in another
   real Compose stack; `repair` still requires operator approval and revision.
5. The public Vercel dashboard is unchanged and remains read-only. This
   integration is **Terminal-only**. The Docker UI buttons are **not** Muse calls.

## Fixed providers and credentials

| `--muse-provider` | Endpoint | Requested model | Local secret variable |
| --- | --- | --- | --- |
| `official-meta` | `https://api.meta.ai/v1/chat/completions` | `muse-spark-1.3` | `MODEL_API_KEY` |
| `baseten` | `https://inference.baseten.co/v1/chat/completions` | `meta-models/muse-spark-open` | `BASETEN_API_KEY` |

`META_BASE_URL` and `META_MODEL` are not accepted as routing overrides, to avoid
credential leakage or accidental calls to arbitrary third-party endpoints.
Keys set in **Vercel** do not automatically exist in your Mac Terminal.
Never paste a secret into ChatGPT, source, shell history or Git. Obtain/set it
privately from the matching provider. Never share `.env` files.

This client uses OpenAI-compatible Chat Completions for both providers. Official
Meta uses `response_format=json_schema` (strict); Baseten requests JSON object
mode and Bravon applies its existing strict local wire validation. Do not
assume Baseten supports schema-constrained decoding without checking.

## Offline verification (NO hosted network requests)

```bash
cd ~/Desktop/proofops-v0.3-real-lab
source .venv/bin/activate
python -m pytest -q tests/test_hosted_muse.py
python -m pytest -q
git diff --check
git status --short
```

The test module mocks both the Docker command runner and the HTTPS calls. It
verifies model choice coverage, wrong action preservation, citations, endpoint
and model selection, CLI consent, rejection, and absence of automatic repairs.

## Documented live trial — official Meta, disposable DNS incident

Operator-provided results from 2026-10-28 (the full JSON evidence remains on
the operator's Mac and is not stored in Git):

- Incident: `4b7094fc1912` on local isolated project `proofops-a-c538bb6404`.
- Fault: CoreDNS returned `10.223.120.99` rather than `10.223.120.10`;
  end-to-end HTTP failed while the Nginx proxy and backend checks passed.
- Hosted Muse Spark 1.3 returned the model-selected `restore_dns` proposal.
  Independent evidence gate accepted it, citing topology, customer-path, DNS,
  gateway, and backend-a observations.
- Hosted investigation: **7** API requests; **3,831 input tokens** and
  **1,638 output tokens** (5,469 total).
- An independent Docker Compose replica reproduced the fault; applying
  `restore_dns` **only in the replica** restored all **5/5** checks without
  changing the active stack.
- After separate explicit human approval and a fingerprint/revision check,
  `restore_dns` was applied **only to the active disposable Docker lab**.
  Incident status became `recovered`, revision advanced to `3`, and all
  **5/5** real active health checks passed; proof result
  `observed-recovery-in-disposable-docker-lab` links to sandbox verification.
- No further hosted model calls occurred during sandbox verification or active
  repair. This is a **single-case** result; other failure modes, fallbacks and
  production runtime behavior still require independent evaluation.

Local operator evidence files (not committed):

- `~/Documents/Bravon-evidence/hosted-muse-dns-drift-v1.json`
- `~/Documents/Bravon-evidence/hosted-muse-sandbox-verification-v1.json`
- `~/Documents/Bravon-evidence/hosted-muse-active-recovery-20261028T142236Z-before.json`
- `~/Documents/Bravon-evidence/hosted-muse-active-recovery-20261028T142236Z-after.json`

**Production caveat:** Vercel's prior `META_BASE_URL`/`META_MODEL` configuration
pointed to Baseten and must be reconciled separately before enabling hosted
inference in the public deployment. The current integration does not activate
hosted Muse in the web dashboard.
## Before any live hosted inference

- Confirm **which provider issued your credential**. A Baseten key is not a Meta
  Model API key; do not guess based on model brand names.
- Confirm account billing/credits, privacy, rate limits, and expected request
  cost. The CLI sends **up to 10 individually potentially billable requests**;
  it has no automatic retries, and records returned token usage without claiming
  that credits are free.
- The only transmitted data are a small fixed set of generated disposable lab
  identifiers and read-only CoreDNS/Nginx/HTTP probe results. No user files,
  real credentials, raw logs, model inputs from other projects, or production
  traffic should be sent. Provider data-handling policies still apply.
- Preserve the old proof, use a currently active unresolved Docker incident,
  and do not concurrently operate the CLI and Docker UI.
- A live call **requires separate deliberate operator approval**; this patch
  does not make one automatically.

## Explicit, optional future live command (DO NOT RUN WITHOUT APPROVAL)

```bash
# In a terminal where the matching provider key was securely set:
python -m proofops.real_lab investigate \
  --investigator hosted-muse \
  --muse-provider official-meta \
  --confirm-cloud 'SEND DISPOSABLE LAB PROBE DATA TO HOSTED MUSE' \
  > /tmp/bravon-hosted-muse-investigation.json
```

Use `--muse-provider baseten` **only** with a matching Baseten credential in
`BASETEN_API_KEY`. An accepted proposal is **not an applied repair**: inspect
`active_incident.raw_action`, `.evidence_gate`, and `.action`, along with
`hosted_model_usage`, before considering a separate replica verification.

## Known limitations

- Chat Completions resends the bounded prior observations each model request;
  it does not preserve hidden reasoning as Meta Responses can. Future Responses
  integration must be evaluated separately, without weakening safeguards.
- No cost estimate or billing assertion is made. No automatic retry/fallback to
  another provider, a paid tier, or a local model.
- OpenAI-compatible endpoints may differ in behavior. Official Meta Muse Spark
  1.3 live structured output and a single disposable DNS-recovery exercise passed;
  **Baseten compatibility remains unverified**. Never send official Meta API keys
  to Baseten or other hosts.
- This is an isolated single-operator demo, not authenticated production repair.

Documentation:
- Meta Model API: https://dev.meta.ai/docs/protocols/chat-completions
- Meta structured output: https://dev.meta.ai/docs/structured-output
- Baseten Muse Spark Open: https://github.com/meta-models/meta-oss-cookbook/blob/main/muse-spark/hosted/baseten.md

## Official Meta reasoning-budget fix

The default Muse Spark reasoning effort can exhaust the output token budget
before a small schema-constrained JSON choice is emitted. Official Meta calls
now set `reasoning_effort=minimal` and `max_completion_tokens=1024` for probe
selection, and `reasoning_effort=low` with 2048 tokens for the final explanation.
Reasoning tokens are counted separately inside billed completion tokens.
Truncation fails closed with no automatic retry. This is a bounded starting
configuration, not proof that live model reasoning will be correct.

The official model and API key are independent of the public Vercel UI, which
remains read-only. Neither test installation nor offline pytest calls a provider.
