# ProofOps v0.2 — Capability-first go / no-go audit

**Status (23 October 2026):** the v0.2 harness is implemented and unit-tested locally. **No live Meta inference has been run by the project authoring environment.** Your Mac reported `APIStatusError` while using the optional v0.1.1 Chat Completions adapter; the status code and cause remain unknown. The old key was exposed in a conversation; **revoke it**, use a replacement only via local environment input, and do not log or commit it.

## Product thesis

**ProofOps — an experimental reliability agent that diagnoses unfamiliar outages through its own read-only investigations, proposes bounded repairs, and passes each candidate through an independent verifier.** The strongest demo would show real, disposable Docker DNS → proxy → backend components, live faults, Meta-selected observations, a safe/declinable repair plan, isolated verification, and an audit-grade before/after transcript.

### Why this fits Meta rather than being a generic AI wrapper

- **Muse Spark 1.3:** Meta documents efficient, agentic tool loops and structured outputs. Use it as a high-frequency investigator that decides which read-only observations to request.
- **Muse Wonder 1.0:** Meta describes a higher-capability model for extended coding and complex, long-running investigations. Escalate ambiguous incidents only after basic observations have been collected.
- **Responses API:** permits multi-step `function_call`/`function_call_output` interactions while preserving investigation context; crucial for experiments where new telemetry changes a hypothesis. Use its `text.format` JSON schema for a typed recommendation. The model cannot directly execute our tools; ProofOps controls execution.
- **Muse Code:** useful as a *developer coding assistant*. It isn't necessary as a hosted run-time for ProofOps.
- **Muse Image / SAM:** image generation and segmentation don't materially improve our DNS/proxy incident demo; do not add them for show. Muse Image is restricted in India under Meta's 12 October policy.

Official documentation: https://dev.meta.ai/docs/models , https://dev.meta.ai/docs/protocols , https://dev.meta.ai/docs/tool-calling , https://dev.meta.ai/docs/structured-output , https://dev.meta.ai/docs/pricing-rate-limits , https://dev.meta.ai/legal/geographic-use-policy .

## Critical defect in v0.1.1

In `proofops/agent.py` the deterministic `evidence_diagnosis(...)` computes the recommended action **before** Meta is called and then passes `permitted_action` into the model's prompt *and* JSON-schema action enum. Meta can only choose the already-computed action or `none`. Even if Meta inference succeeded, it would not establish that the model independently discovered the fault or selected a fix. And v0.1's 30 synthetic recoveries are state-machine tests, not agent capability benchmarks.

**New v0.2 capability test:** Model sees the same generic incident description for every case, receives a menu of **read-only** diagnostic tools and chooses which observations to collect. The expected root cause and repair label remain entirely local to the scorer. The model may propose one repair, or abstain. No repair actions are executed during this evaluation.

## Six blind synthetic test cases

| Case | Hidden state | Safe one-step action |
|---|---|---|
| `dns_drift` | DNS record points away from gateway | `restore_dns` |
| `proxy_misroute` | Proxy points at an undeclared backend | `restore_proxy` |
| `backend_outage` | Primary down but standby healthy | `failover` |
| `healthy` | Request path operational | `none` |
| `compound_fault` | DNS **and** proxy broken | `none` — one action doesn't restore health |
| `no_standby` | Both backends down | `none` — unsafe to fail over |

Tools available: `inspect_topology`, `lookup_dns`, `inspect_gateway`, `probe_backend`, and `probe_customer_path`. Each returns synthetic observations with evidence IDs. The requested action is **not** included in any tool result. The model's `evidence_ids` are validated against the observations actually returned.

A rigorous evaluation counts **every error** as a failed attempt. It reports per-case action accuracy, number of model-selected probe calls, evidence validity, API tokens, elapsed time, and estimated token cost. Note that an accurate *proposal* is not a verified repair and synthetic cases cannot establish production reliability.

## On your Mac (from the repository folder)

Set a replacement API key in the local terminal only; **do not include the key in a command line, GitHub repo, transcript, or screenshot**:

```bash
cd ~/Desktop/proofops-starter
source .venv/bin/activate
printf 'New Meta API key: '; read -rs MODEL_API_KEY; echo
export MODEL_API_KEY
python -m pip install -e '.[dev,meta]'
```

To preview benchmark cases **without any API requests or charges**:

```bash
python -m proofops.frontier_eval
```

To troubleshoot the previous `APIStatusError` with just **one small real Responses request** (may be billed):

```bash
python -m proofops.frontier_eval --live --check --models muse-spark-1.3
```

If successful, try Muse Wonder (may be billed):

```bash
python -m proofops.frontier_eval --live --check --models muse-wonder-1.0
```

To run the actual **paid** model evaluation on the six blind synthetic cases:

```bash
python -m proofops.frontier_eval --live --models muse-spark-1.3 \
  --output reports/spark-1.3.json
```

To compare against Muse Wonder (additional paid usage):

```bash
python -m proofops.frontier_eval --live --models muse-wonder-1.0 \
  --output reports/wonder-1.0.json
```

Share the summary and errors only; **never** your API key. The evaluation reports contain no key. Do not claim completion until the live reports actually exist.

## Acceptance gates for continued investment

1. **Connectivity**: one small successful Responses API call with replacement credentials. Errors must include class and HTTP status, not hidden as an untyped fallback.
2. **Model differentiation**: score Spark and Wonder on the same hidden six-case suite. A reasonable pilot target is at least 5/6 correct actions **and both unsafe cases abstained**, using at least two inspections for affected cases. Threshold is a design goal, not achieved performance.
3. **True environment**: replace all synthetic observations with Docker CoreDNS/Nginx/FastAPI services. Demonstrate observed HTTP/DNS path faults, not just in-memory config changes.
4. **Independent proof**: model proposes action without being told the answer; sandbox validates; a separate deterministic judge checks before/after probes and regression tests; rollback on failure.
5. **Unseen evaluation**: introduce held-out scenarios the prompt doesn't enumerate, including compound fault, healthy-but-latent probe, and unsafe-repair bait; report all failures and costs transparently.

## Competition and safety boundaries

- **Hackathon judges**: Indie track evaluates creativity, technical ambition and working functionality. These criteria appear on the event page, but **official rules are not published before October 26**. Check restrictions on pre-event work and teams before submission.
- **Competitive landscape**: incident investigation and recovery already exist in AWS DevOps Agent and related SRE products. We shouldn't claim we invented autonomous troubleshooting. The differentiation is a *reproducible causal experiment*, strict separation of model proposal from verification, refusal to apply unsafe plans, and portable proof packets.
- **Not production ready**: the current FastAPI dashboard is unauthenticated and in-memory; keep it bound to `127.0.0.1`. No Docker socket, arbitrary shell, production credentials, or destructive model-issued actions.
- **Geography**: Meta's October 12, 2026 Model API geographic policy restricts service use from Mainland China, Hong Kong and Macau, among other locations. If you're traveling there during the hackathon, arrange a compliant plan with the organizers. Never bypass access controls.
- **Pricing (standard)**: per 1M uncached input/output tokens, Spark 1.3 $1.25/$4.25; Wonder 1.0 $4/$20. Actual spending depends on reasoning/tool turns; the harness caps turns and reports estimated uncached token spend.

## What is built now, and what remains

**Built in v0.2:** isolated read-only tool registry; Responses API multi-step harness; schema-validated repair proposal; hidden-label six-case scorer; refusal cases; sanitized HTTP error category, offline unit tests; dry-run default; token/latency/cost metrics.

**Not yet built/tested:** live inference in this authoring environment, Docker production-like lab, real repair execution, held-out real incident benchmark, proof packet signing/attestation, public deployment, accepted hackathon entry.
