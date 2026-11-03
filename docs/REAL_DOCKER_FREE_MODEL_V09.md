# ProofOps v0.9 — opt-in free-model investigation of disposable real Docker evidence

This connects the previously qualified *synthetic* Nemotron investigator to the existing isolated ProofOps Docker lab **without automatically repairing anything**. Model accuracy on physical Docker probes is still unverified until the operator runs a real Mac trial.

## Why this is a separate security boundary

The synthetic test sends generated fixture observations; this new CLI **sends actual read-only probe results from disposable containers to OpenRouter**, a third-party inference provider. The values are fixed and bounded:

- Static lab hostname `app.proofops.test`, generated Docker-private `10.223.<slot>.*` IP addresses and declared backend names
- End-to-end HTTP health boolean and selected backend label
- Observed CoreDNS answer and expected gateway IP
- Nginx upstream address, allowed-address boolean and declared backend addresses
- Direct backend A/B health boolean

It does **not** send arbitrary shell commands, environment variables, API keys, container logs, source files, real user traffic, personal files, Docker socket access, or production telemetry. There are no published ports on the Docker network. This is a **terminal-only** opt-in, never enabled by starting the dashboard or setting the API key alone. OpenRouter's own retention/training policy applies to the submitted bounded observations; run only in the disposable local lab.

Model: exact `nvidia/nemotron-3.5-lightning:free`, no paid fallback or model router. Maximum 10 hosted requests for an investigation. Free quota/rate limits can stop an investigation. No background requests or automatic retries are performed.

## Where the gate sits

```text
real CoreDNS / Nginx / backend / customer probes (read-only)
      ↓  fixed bounded evidence only — after operator confirms upload
free hosted Nemotron tool selection / raw final proposal
      ↓
strict schema, allowlisted commands & observed citations
      ↓
independent evidence gate (semantic conditions; no fixture labels)
      ├── DENIED: preserve raw decision, store promoted_action='none'; verify blocked
      └── ACCEPTED: store promoted allowlisted repair, but do not execute
                  ↓ (another explicit CLI/UI operator step)
independent second Docker Compose verification stack
                  ↓ (separate approval with exact phrase and revision)
active repair + post-repair probes + rollback on failure
```

The rule-based `analyze` command remains available as a separate operator choice. It resets any prior investigation provenance and cannot be confused with a hosted model decision.

## Mac runbook

From `~/Desktop/proofops-v0.3-real-lab`:

```bash
source .venv/bin/activate
python -m pytest -q
# Must have Docker Desktop running; this does not call the model:
docker info
python -m proofops.real_lab status
```

If the lab has never been started (and `status` says so), run `python -m proofops.real_lab start`. If an unresolved incident is already active, do **not** inject again; investigate it or explicitly reset first. Otherwise:

```bash
python -m proofops.real_lab inject --scenario dns-drift
```

Enter the OpenRouter key privately into the **same** terminal shell if it is not already present:

```bash
printf 'OpenRouter key: '
read -rs OPENROUTER_API_KEY
echo
export OPENROUTER_API_KEY
```

Then choose to **explicitly upload fixed disposable lab probe data**:

```bash
python -u -m proofops.real_lab investigate \
  --investigator openrouter-free \
  --confirm-cloud 'SEND DISPOSABLE LAB PROBE DATA TO OPENROUTER'
```

This is the only step that contacts OpenRouter. It is capped at 10 `:free` requests. It **does not repair** anything. Inspect `active_incident.raw_action`, `.evidence_gate`, and `.action`, plus `hosted_model_usage` in the CLI output. The raw action remains verbatim; `action` is only populated with a repair name after the independent gate accepts it.

For the UI, start the existing loopback-only server **after** the CLI command (do not modify the lab concurrently from another terminal):

```bash
PROOFOPS_ENABLE_DOCKER_UI=1 PROOFOPS_PORT=8001 ./scripts/start-local.sh
```

Open <http://127.0.0.1:8001/docker>. It shows the hosted model's raw and promoted proposals, citations, and evidence gate. **The page's “Investigate with tools” button still invokes the offline rule-based reference investigator; pressing it overwrites the currently displayed free-model proposal.** Never expose this server on the network. If the gate accepted a non-none repair, click **Verify in replica** to reproduce and test it in the second Docker stack, then decide whether to **Approve & repair**. The app still requires separate approval, expected revision, and proof of sandbox recovery.

The same steps are available explicitly in CLI:

```bash
python -m proofops.real_lab verify
python -m proofops.real_lab status
# Only after sandbox success, replace REV with the exact revision from status:
python -m proofops.real_lab repair --revision REV --confirm 'APPLY TO LOCAL DOCKER LAB'
```

A wrong, unsupported, incomplete or uncited model repair cannot reach `verify`. A qualified proposal still cannot bypass sandbox verification or approval.

## Offline acceptance vs real outcomes

Offline unit tests use `FakeDockerRunner` and scripted model decisions; they prove **integration boundaries** (consent, model provenance, fail-closed evidence, and sandbox/human approval). They do *not* prove live Nemotron accuracy on the Docker network. The operator's latest **separate synthetic cases** were 3/3 correct, 0 unsafe, and 21 `:free` model requests; this is not an unseen-data generalization claim.

No Docker daemon or external API key is present in the packaging environment. The Mac trial must be reported separately using its actual measured output.
