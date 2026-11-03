# ProofOps v0.5 — Read-only investigation substrate

**Status:** implementation and unit tests complete with FakeDockerRunner. The user's v0.4.1 real-Docker qualification passed **3/3 known fault recoveries** on their Mac. **v0.5 read-only tool calls against the real Docker daemon remain unverified** until a new acceptance run is performed. No Meta credentials are needed, and **no AI inference is performed in v0.5**.

## What changed

A new route and CLI action, `investigate`, accept an unrecovered incident. A bounded reference investigator requests observed facts using a tool interface, then proposes one of `restore_dns`, `restore_proxy`, `failover`, or `none`.

- Tool `topology`: declared service addresses only (no state/config fault hints)
- Tool `customer_path`: direct client-to-gateway HTTP probe over the private Docker network
- Tool `lookup_dns`: CoreDNS query issued by the disposable probe container
- Tool `inspect_gateway`: selected Nginx route from `nginx -T`
- Tool `probe_backend` with `backend-a` or `backend-b`: exact allowlisted direct HTTP health checks

No arbitrary command strings, hosts, URL paths, shell arguments or writable tools are accepted from an investigator. Each returned observation carries an evidence ID. A final repair proposal must cite observed IDs, match a known action, and satisfy type/length/budget constraints.

The initial `ReferenceInvestigator` **always follows a fixed six-tool plan**; this is a transparent rule baseline, **not an AI agent** and not proof of model capability. The provider-neutral `InvestigatorAgent` protocol will allow model-directed tool selection later, after a properly authenticated Meta account becomes available. The model must never receive `incident.scenario`, controller state `config`, or the expected action as an input. The integration preserves independent sandbox verification and operator approval.

## Real Docker acceptance on Mac

1. Restart the ProofOps server after applying the patch; leave Docker Desktop running. Do not operate the dashboard while using the CLI.
2. From the project's root with the virtual environment active, run:

```bash
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
python -m proofops.real_lab status
```

3. Proceed only if the output has `"service_status": "healthy"`, `"active_incident": null` and five passing checks. Do not reset unexpectedly unhealthy services without inspecting them.

4. Then use the existing disposable stack:

```bash
python -m proofops.real_lab inject --scenario dns-drift > /tmp/proofops-v05-fault.json
python -m proofops.real_lab investigate > /tmp/proofops-v05-trace.json
python - <<'PY'
import json
with open('/tmp/proofops-v05-trace.json', encoding='utf-8') as f:
    incident = json.load(f)['active_incident']
report = incident['investigation']
print('Source:', incident['diagnostic_source'])
print('Proposed action:', report['proposal']['action'])
print('Read-only tool calls:', report['tool_calls'])
print('Evidence references:', ', '.join(report['proposal']['evidence_ids']))
print('Repair executed during investigation:', report['executed_repair'])
PY
```

5. If the proposed action is `restore_dns` and the trace is internally plausible, use the existing independent sandbox verification and explicit approval:

```bash
python -m proofops.real_lab verify > /tmp/proofops-v05-verification.json
REVISION=$(python -m proofops.real_lab status | python -c 'import json,sys; print(json.load(sys.stdin)["revision"])')
python -m proofops.real_lab repair --revision "$REVISION" --confirm 'APPLY TO LOCAL DOCKER LAB' > /tmp/proofops-v05-recovery.json
python -m proofops.real_lab status | python -c 'import json,sys; s=json.load(sys.stdin); print(s["service_status"],sum(c["passed"] for c in s["checks"]),"/",len(s["checks"]))'
```

6. If anything fails, inspect the exact error; use `python -m proofops.real_lab status`. `reset` is available for *only the disposable lab*, but avoid masking a failed acceptance run. Share the saved trace and recovery JSON with credentials removed for independent inspection.

## Trust boundaries

- **Reference investigator:** 100% local deterministic policy. No model, no token usage, no paid service, no claim of novel reasoning.
- **Read-only tools:** fixed internal Docker Compose `exec` probes, bounded to six tool calls by the baseline (eight maximum), without arbitrary shell or external network access.
- **Recorded trace:** bounded, cited observations; evidence IDs establish provenance within the local controller, not cryptographic tamper resistance.
- **Independent verification:** existing v0.4.1 cloned-Docker verification must pass before repair; an incorrect proposal is not automatically executable.
- **Manual approval:** existing `approved`, revision, fingerprint and confirmation checks still gate any mutation to the disposable active stack.
- **Local API:** Docker access disabled by default, extra loopback/origin/intent checks if enabled. This is a developer lab, not secured multi-tenant production infrastructure.

## Limitations and next milestones

The reference policy deliberately examines a full set of signals, so it does **not** optimize tool selection. This is only the substrate for a later model-selected tool loop. The local fake-Docker tests cover healthy/no-op and compound-fault abstention but cannot prove those conditions on Docker Desktop. Only a successful Mac acceptance run would establish that the v0.5 tool layer works against real containers.

Next: integrate Meta Responses with a constrained `InvestigatorAgent` adapter after account billing/credits work; add blind held-out faults, competing hypotheses, repeated live reliability trials, bounded costs, latency metrics, and adversarial safety evaluations. A local deterministic policy is only a baseline and cannot be presented as an AI benchmark result.
