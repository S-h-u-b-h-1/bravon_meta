# ProofOps — 10-day execution roadmap

**Pre-event v0.1 (October 23):** complete deterministic local incident lab, API, working dashboard, guarded repair flow, offline evidence engine, optional Meta adapter, tests. Treat as a **preparation prototype**, pending official rules governing pre-built work.

## Milestone 1: Actual observed services (Oct 26–27)

- Docker Compose: CoreDNS resolver, Nginx gateway, backend A/B, probe worker.
- Real DNS and HTTP commands executed from isolated client container; capture response status, latency, target identity, config version and raw redacted logs.
- Controlled fault injection (wrong DNS record, invalid Nginx upstream, Backend A process unavailable).
- Restore reproducibly from clean image; never edit the user's real DNS, Nginx, or other host services.
- Ensure observations explicitly distinguish `UNKNOWN` vs `FAIL` vs `PASS` (do not turn missing telemetry into success).
- Benchmark healthy / faulty / recovered behavior for each scenario.

**Exit criterion:** three failures reproduced and corrected in the disposable environment with actual traffic and automated regression tests. No fabricated 200 responses.

## Milestone 2: Reasoning as a guarded agent (Oct 28–29)

- Meta Muse Spark as the default first-pass analyst, Wonder for complex multi-hop incidents only if available and within quota.
- Add bounded read-only tools (`read_probe_results`, `inspect_service_config`, `get_redacted_logs`, `view_topology`). Model requests are parsed, schema validated, budgeted and audited.
- Keep execution behind explicit typed repair catalog and human approval; model never authors arbitrary shell commands for execution.
- Harness for wrong actions, hallucinated evidence IDs, injection text in logs, incomplete diagnostics, provider downtime and timeout.
- Measure model vs deterministic baseline on unseen perturbations; blind test set; log token consumption and end-to-end latency.

**Exit criterion:** valid analysis with traceable citations to real observation IDs; fallbacks surfaced honestly; no unsafe action through adversarial outputs.

## Milestone 3: Real verification and rollback (Oct 30–31)

- Disposable cloned Docker environment, candidate configuration, `nginx -t`, service-level tests, and E2E availability probes.
- Pre-apply snapshot; atomic apply; independent post-change checks; bounded rollback if any guard fails.
- Cryptographic hashes for trace integrity; distinguish signed attestation from plain checksum.
- Add approvals, audit events, and test logs to SQLite or Postgres for persistence.

**Exit criterion:** fix successfully repairs real disposable outages; proof includes actual source observations + before/after traffic and exit codes.

## Milestone 4: Judge-ready experience (Nov 1–2)

- Polish graph, incident player, causal chain and what-changed diff.
- Script and record <3 minute compelling demonstration with one unexpected failure.
- Document costs, constraints, gaps, and safety boundaries.
- Cross-platform startup (`make demo`) and CI end-to-end test on GitHub Actions.

## Milestone 5: Benchmark + submission (Nov 3–4)

- 30+ real runs across fault categories, withheld conditions and a no-fix/unknown class.
- Report diagnosis precision, recovery success, MTTD/MTTR, safe refusal rate, and latency distributions with confidence intervals.
- Submit only eligible work, following published contest rules and location requirements.

## Risks and mitigation

1. **Hackathon code provenance:** Official rules scheduled for Oct 26; record commits/creation dates; honor any restrictions on pre-existing code. If required, rebuild the entry during allowed dates rather than relabeling this prototype.
2. **API access and cost:** Opt-in Meta integration, no pre-filled key, clear offline fallback, token budgets.
3. **Geographic restrictions during travel:** Check location policies; do not attempt circumvention.
4. **Too much scope:** Favor 3 deeply tested real incident types over 20 scripted fakes.
5. **Safety:** The environment must remain disposable; never connect destructive actions to production credentials.


## v0.5: Read-only investigations (implementation tested, Docker acceptance pending)

- `proofops.investigation`: validated tool-call/proposal interface and real-stack read-only probes
- Deterministic reference agent and evidence-linked trace, no Meta calls
- Existing independent sandbox verification and approval remain mandatory
- Next: verify the new tools against Docker Desktop, connect a bounded model adapter only after credits/access become available, and blind-test novel or compound faults

## v0.6 checkpoint (October 23, pre-hackathon)

- Added seeded, bounded, local **synthetic** read-only evaluation harness and two NON-AI rule baselines.
- Measured safe abstention, wrong repair proposals and number of diagnostic calls on known fixture families.
- Added evidence replay and strict metadata checks; a checksum is **not a signature**.
- Added optional `--investigator adaptive` to the **disposable** Docker CLI (not production).
- Next: qualify adaptive against Mac real Docker probes; freeze independent unseen incident set; integrate Meta only with valid credits and explicit runtime selection.

## v0.7 checkpoint (October 23, pre-hackathon)

- Strict provider-neutral JSON output protocol with read-only allowlist, evidence citations and bounded turn budgets.
- Deterministic wire emulator, adversarial protocol tests and seeded local replay evaluation (NOT AI).
- Opt-in `OllamaLocalProvider` for a locally running Meta Llama open-weight model; no external API credentials.
- Real Docker CLI accepts explicit `wire-emulator` and `ollama-local` investigators; all proposals remain subject to the unchanged second-stack verifier and approval gates.
- Next: run local Llama on Mac, measure actual failure/error rates on the synthetic cases and one real Docker incident, then curate independent unknown faults.
