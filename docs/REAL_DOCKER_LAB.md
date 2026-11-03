# ProofOps v0.3 — Real Docker infrastructure milestone

## Proven, and not yet proven

- **Implemented:** separate Docker Compose network; CoreDNS authoritative host entry; Nginx reverse proxy; two Python HTTP backends; probe client; three allowlisted faults; actual DNS, Nginx and HTTP probes; two-stack verification; explicit operator approval; revision/config/probe fingerprint; rollback attempt and before/after proof packet; localhost-only UI.
- **Verified here:** 58 offline unit/API tests and JavaScript syntax (using a fake Compose runner). The existing simulation and Meta capability harness remain intact and unmodified in their core semantics.
- **NOT verified here:** Docker Desktop cannot run in this authoring environment. A true multi-container end-to-end test must be executed on a Mac with Docker Desktop. Do not report real recovery until that run passes and the exported proof shows actual observations.
- **Not implemented:** AI model-driven investigation in the *real* stack, production credential access, durable distributed locks, signed attestations, general-purpose command execution, or a publicly hosted authenticated system. `analyze` intentionally uses rules over observed probes while Meta credentials are unavailable.

## Requirements

- macOS with **Docker Desktop** running (`docker info`, `docker compose version` should work).
- Python 3.10+ (3.12 or 3.13 recommended), a local terminal, room for several small container images.
- Internet access for the **first Docker image pulls** and building the tiny Python server. No inference API key, database or GPU needed.
- Compose creates an **internal-only bridge** with `10.223.120.0/24` for active and `10.223.121.0/24` for verification. If these overlap your VPN / existing Docker networks, use `--slot 150` for active `10.223.150.0/24` and verification `10.223.151.0/24` (20–219 allowed). Do not forward or publish container ports.

## Recommended Mac workflow (two terminals)

First, use a clean v0.3 folder, not a merge of v0.1 source. Or apply the version-specific upgrade patch after a dry run.

```bash
cd ~/Desktop/proofops-v0.3-real-lab
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
./scripts/test-real-lab-offline.sh

docker info
docker compose version
python -m proofops.real_lab start
```

The `start` command initializes a disposable network, builds two small backends, and **fails** unless all five actual probes pass. The output includes a private Compose project name. No container port is exposed on the Mac.

To drive everything by CLI:

```bash
python -m proofops.real_lab inject --scenario dns-drift
python -m proofops.real_lab analyze
python -m proofops.real_lab verify
python -m proofops.real_lab status
```

The verification operation creates a **second, independent Compose network**, reproduces the fault, tests the proposed repair, and tears down the second stack. The active stack remains damaged until approval. To approve, use the *current* revision printed by status (replace `REV` with that integer):

```bash
python -m proofops.real_lab repair --revision REV --confirm 'APPLY TO LOCAL DOCKER LAB'
```

Or use the interactive browser:

```bash
PROOFOPS_ENABLE_DOCKER_UI=1 PROOFOPS_PORT=8001 ./scripts/start-local.sh
```

Open **http://127.0.0.1:8001/docker**. The UI is opt-in because the local web process then has permission to invoke tightly scoped Docker CLI commands. It will not automatically start containers. Run a scenario, Analyze, Verify, and explicitly approve the repair. Download the proof JSON after the post-repair health checks pass.

You can repeat with:

```bash
python -m proofops.real_lab inject --scenario proxy-misroute
python -m proofops.real_lab analyze
python -m proofops.real_lab verify
# Explicitly approve via UI or repair command, then repeat backend-outage
```

To return to a known-good state:

```bash
python -m proofops.real_lab reset
python -m proofops.real_lab stop
```

`stop` removes only the two **known project names** from the local ProofOps state. Runtime files and proof checksums are retained under `.proofops-runtime/`, which is gitignored. To inspect Compose runtime status without running host-wide destructive commands, use the project name printed by `status`:

```bash
docker compose -f infra/compose.yaml -p YOUR_PROOFOPS_PROJECT ps
```

Note: for this manual command you must also supply the stack's `PROOFOPS_*` Compose environment values (easiest: use the `proofops-docker status` command instead). The app automatically supplies those values to its own Compose calls.

## Safeguards and limitations

1. **Internal Docker networks only.** Compose has no `ports:`, host networking, privileged containers or socket mounts. The host CLI still needs ordinary permission to access Docker Desktop.
2. **No model-generated shell.** Exactly `restore_dns`, `restore_proxy`, and `failover` can be applied. They only change known DNS/Nginx files or stop/start the known backend A Compose service.
3. **Separate replica.** Validation is done by a second network and project with its own CoreDNS, Nginx, HTTP backend and probe containers, not by mutating active services.
4. **Revision + fingerprint.** Observed DNS, Nginx routing, direct backend HTTP, end-to-end HTTP and standby health are included. Any observed change rejects stale repair authorization. These are checksums, not tamper-proof signatures.
5. **Rollback attempt.** Failed post-apply health checks restore the previous generated configurations and backend A state. If rollback itself fails, the controller records `rollback-failed` and requires manual inspection; it does **not** claim recovery.
6. **One operator.** State is a local JSON file with atomic writes but not a cross-process distributed lock. Do not concurrently operate via CLI and UI in this milestone.
7. **Local-only web permissions.** Docker mutation API is disabled by default and refuses cross-origin or requests without a custom local-intent header. Nonetheless it is not authenticated for multiple users; keep Uvicorn bound to `127.0.0.1`, never deploy as-is.
8. **No secrets.** The stack consumes neither `MODEL_API_KEY` nor other provider credentials. Leave API integration disabled while billing/credits are unresolved.

## Debugging on Docker Desktop

- `docker info` must succeed before starting.
- If image pulls fail, check network access and Docker Desktop disk allowance.
- If subnet allocation fails, stop the lab and choose `--slot 150` (or an unused 20–219). Pass the same root and optionally slot for all subsequent commands.
- If CoreDNS has not reloaded, controller waits/retries for at most 12 seconds. Actual CoreDNS hosts-file reloading is documented at https://coredns.io/plugins/hosts/.
- If an experiment does not yield passing probes, **don't bypass verification**. Inspect `docker compose ... logs` with project/environment values from a valid stack or share the sanitized CLI error text.
- If port `8000` is already taken by old ProofOps, use `PROOFOPS_PORT=8001` as shown above; the Docker services publish no Mac port.

## Acceptance test to run next on a real Mac

- Initial `start`: **5/5** true Docker probes.
- All three faults individually: reproducible red state; per-fault observed evidence; sandbox reproduces the same failure signature.
- `verify`: independent network passes **5/5** and does not repair active.
- `repair`: only exact approval + matching revision succeeds; proof records before/after results.
- Drift: changing an active lab config after verification rejects the apply request.
- Stop: all ProofOps containers are removed without affecting unrelated Docker projects.

Until this checklist is observed in Docker Desktop, the milestone is an **implemented but not runtime-qualified** real-lab candidate.
