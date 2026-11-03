# Bravon — Owner-approved ephemeral Docker qualification

## Status and scope

This is an opt-in **GitHub-hosted Docker** runner prototype, not a public website feature, a production self-healer or a Meta Muse invocation.

It runs the existing deterministic, real-probe qualification on **new disposable Docker Compose projects** inside one ephemeral GitHub-hosted Ubuntu runner. No account, customer, local Mac Docker socket, Vercel instance or external infrastructure receives a repair.

- Three hardcoded scenarios: DNS record drift, proxy misroute, primary backend outage.
- Fixed allowlisted rule-based repairs only; **zero AI or hosted model requests**.
- A separate disposable verification stack checks repairs; unapproved and stale-revision actions must be denied.
- Active stack must return to five passing probes after every scenario; cleanup must complete.
- Full Docker telemetry remains inside the ephemeral runner. Only a tiny, fixed-schema minimized receipt can be uploaded as a **private GitHub Actions artifact**.
- An uploaded receipt is self-digested controller evidence, **not independent third-party/hardware attestation**.

This is distinct from the private official Muse Source A / Immortality System B records.

## Authorization model

The workflow at `.github/workflows/remote-docker-qualification.yml` is **workflow_dispatch only** and never runs on a push or PR.

The following conditions must all agree:
1. Repository: `S-h-u-b-h-1/bravon` and branch `main`.
2. Event: explicitly requested `workflow_dispatch`, never `push` or PR.
3. Both original `GITHUB_ACTOR` and `GITHUB_TRIGGERING_ACTOR` must be the
   repository owner `S-h-u-b-h-1`, including when a job is re-run.
4. Owner-entered confirmation: `RUN BOUNDED REMOTE DOCKER QUALIFICATION`.
5. Owner-set **repository configuration variable**
   `BRAVON_REMOTE_RUNNER_ENABLED` must be exactly `YES`.
6. GitHub run ID/attempt/source commit must be valid, and an actual normal
   `RUNNER_TEMP` directory must exist.

**The repository opt-in variable is intentionally unset by default.** The
owner must explicitly enable it in the private repository's Actions settings.
No public HTTP request, Vercel page, PR comment, arbitrary GitHub account or
model can dispatch the actual Docker experiment.

**Why this uses a repository variable instead of an environment reviewer:**
GitHub documents that required environment reviewers on Free/Pro/Team
subscriptions are available only for **public** repositories, and private
environment availability itself depends on plan. This private prototype must
not silently require an unavailable paid feature. The fallback uses the
stronger actor/re-run checks, an explicit typed consent and repository opt-in.
It is still **single-owner authorization, not an independent second-person
approval**.

Documentation:
- https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-variables

The workflow's token has read-only `contents` permission. No GitHub or
Vercel public endpoint can trigger remote Docker, and no cloud/model API key
is requested. Do not enable repository execution until the owner approves the
exact code, image digests, and CI evidence.

## Owner setup — only after review and merge

1. Complete code/security review. The workflow must exist on the reviewed
   default branch for its **Run workflow** button to be available.
2. In GitHub, open **Settings → Secrets and variables → Actions → Variables**.
   Add the **repository** variable `BRAVON_REMOTE_RUNNER_ENABLED=YES`.
   This is an explicit owner decision; keep it unset until you intend to
   permit real disposable runner execution. It is not a credential.
3. In **Actions → Bravon — Owner-approved ephemeral Docker qualification**,
   select `main` and choose **Run workflow** while signed in as the owner.
4. Select exactly one known scenario first, preferably `dns-drift`, and type
   the confirmation phrase exactly. Do not use an unreviewed `all` run.
5. Review the result, independent-clone checks and cleanup record. Download
   the private artifact `bravon-disposable-qualification-<run id>` only after
   the run completes successfully. Do **not** publish it automatically.
6. Reset `BRAVON_REMOTE_RUNNER_ENABLED` to an empty/unset value after the
   qualification window to disable any further dispatches.

For higher-assurance deployments on a plan supporting protected private
environments and separate required reviewers, add those controls after an
explicit design/security review rather than assuming they're available.

Before dispatching, the following no-execution plan can be inspected:

    python -m proofops.remote_qualification --scenario dns-drift --plan

The plan command does not contact Docker, GitHub Actions or Meta.

## Evidence and interpretation

The receipt schema is `bravon.remote-docker-qualification.v1`. It contains:
- selected scenario(s) and fixed allowed action(s)
- five exact probe IDs with pass/fail booleans before, after isolated verification and after recovery
- booleans confirming unapproved/stale repairs were denied and each scenario reset to healthy
- GitHub run ID, attempt and commit, plus internal controller/receipt content digests
- explicit provenance and scope limitations

It does **not** copy Docker stdout, container addresses, raw logs, user paths, model data, API keys, environment dumps, shell traces, IPs, URLs or private network topology.

The raw qualification report is used to compute the receipt and is destroyed with the temporary working directory. A failed or incomplete experiment **must not** produce a green private receipt. The workflow refuses to upload if the script returns a nonzero exit code.

A self-consistent receipt can still be fabricated by an actor controlling the runner or repository. It should be presented as **GitHub Actions controller evidence**, not a signed independent attestation or measured general repair rate.

## Security and operational blockers

- The three public `infra/compose.yaml` images and backend Dockerfile are digest-pinned. The former Nginx 1.28 image was replaced with patched **NGINX 1.30.6 on Alpine 3.24** using its current Docker Hub index digest. See `docs/REMOTE_IMAGE_LOCK.md`. This reduces known exposure but **does not establish that the exact new image is vulnerability-free**; SBOM/CVE review, actual digest pull and five-probe real Docker requalification remain blocking.
- The daemon runs on a GitHub-hosted VM, not a secure multi-tenant customer sandbox. The workflow trusts reviewed code on protected `main`; do not allow arbitrary customer jobs, Git refs, patches, image names, scripts or IPs.
- The job uses GitHub-hosted Docker and fetches known container images. The inner Compose network is `internal: true`, with no host-published application ports or container Docker socket.
- All four external container references use immutable SHA-256 digests from recorded registry references. The image contents must still be validated by a real Docker pull/build and vulnerability inspection on the intended runner architecture.
- Every disposable Compose service has a fixed **256 MB memory**, **1 CPU** and **64 PID** limit (including verification clones). These are hard resource ceilings, not performance guarantees; validate actual resource behavior before using the remote qualification evidence.
- No arbitrary workload, code patch or unbounded command can be supplied as an Actions input.
- Use one run at a time; the concurrency group serializes dispatches. The 25-minute job timeout and per-Docker-command timeouts bound execution.
- On errors the controller attempts to stop known disposable stacks. The remote controller now traps **SIGTERM and SIGINT** to request best-effort cleanup before returning failure; it also refuses to export any green receipt on cancellation. **SIGKILL, abrupt host loss and hard runner shutdown cannot be intercepted**, and GitHub may force-kill a job before Docker cleanup finishes. Ephemeral VM disposal is a secondary boundary, not proof of clean teardown.
- Do not add paid hosted Muse credentials to this environment; no model request occurs.
- Do not expose raw/controller output or an unauthenticated workflow dispatcher from Vercel. To let a jury see remote physical results, **publish only a separately reviewed minimized receipt or a documented read-only playback**, not direct workflow execution.

## Offline source verification without GitHub Actions

A read-only local release check is available to avoid depending entirely on
paid/limited GitHub Actions compute. It uses only the **already-installed**
Python development environment and Node.js. It does not perform a `pip install`,
pull Docker images, start Docker, call hosted Muse, dispatch Actions, upload
reports, or require GitHub billing to be healthy.

From the repository root:

    source .venv/bin/activate
    bash scripts/offline-release-check.sh

It performs:
- Python syntax parsing across project/tests/QA without creating a container
- JavaScript syntax checks on the major frontend scripts
- Browser UI unit tests for model and remote evidence (no real browser)
- Python fake-Docker authorization/privacy/qualification contract tests
- The remote controller's no-execution plan and Git whitespace checks
- A loopback-only FastAPI HTTP integration smoke: seven jury routes, every
  referenced JavaScript/CSS asset, CSP/security headers, API evidence mode,
  and denial of four server-side mutation endpoints. No Chromium/Docker/Muse.

### Executed independent HTTP evidence (2026-10-31)

An isolated Vercel Sandbox ran `python3 qa/http_smoke.py` using a
temporary source snapshot fetched from PR #11. Python 3.14, FastAPI and
Uvicorn were installed for test execution. Network access was disabled
during the HTTP checks; the local app bound only to `127.0.0.1`.

- **PASS (executed prior to the final diagnostic hardening):** seven route
  entries, representing **six distinct HTTP server paths** plus the
  `/#tour` client-side hash entry (including Docker, Muse, Immortality and Model Trials).
- **PASS:** 19 HTML-referenced CSS/JavaScript assets, security response
  headers and public evidence mode. The newest script additionally verifies
  `/api/docker/status.enabled == false`, removes inherited provider credentials,
  and distinguishes server routes from hash navigation; those refinements
  require an exact-head execution before final sign-off.
- **PASS:** four mutation endpoints returned HTTP 403. The test made no
  actual Docker calls, model requests or uploads.
- **Negative control:** temporarily hiding `web/docker.css` caused the
  test to fail with `/assets/docker.css: HTTP 404`; restoring it
  restored the pass. The error now names the failing route/asset.
- Added offline unit tests in `tests/test_http_smoke.py` to reject unsafe
  asset references, weak CSP, accidentally enabled public Docker and
  unexpected HTTP 2xx mutation responses. These latest unit cases have
  not yet passed an exact-head release run.

This is **real loopback HTTP/ASGI integration evidence**. It does **not**
certify layout in a rendered browser, cross-browser accessibility, true
GitHub-hosted Docker execution, vendor model inference or independent
attestation. The separate Playwright browser smoke remains a release gate;
a Vercel Sandbox Chromium attempt was blocked by its Ubuntu runtime
dependencies and the ephemeral session ending before the rerun.

**This is not real Docker or headless Chromium validation**, and a success
from the owner's Mac or a separate runner must not be described as the
GitHub Actions CI badge being green. Save the exact command output and source
commit when reviewing a release. Dependencies must be installed separately
from reviewed constraints.

### Lock the remote Docker endpoint to the runner

The original `DockerLab` can inherit Docker CLI configuration from its
execution environment. For a remote GitHub-hosted experiment, the remote
controller now **requires** `DOCKER_HOST=unix:///var/run/docker.sock`
and refuses any nonempty `DOCKER_CONTEXT`, `DOCKER_CONFIG`,
`DOCKER_TLS_VERIFY` or `DOCKER_CERT_PATH`. It also requires a local
Unix socket before invoking Docker. This prevents a workflow variable from
silently redirecting the disposable experiment to a customer or other
external Docker engine. Unit tests cover both the refusal and the exact
`docker --host unix:///var/run/docker.sock info` preflight.

The runner's Docker identity is still *controller-reported*, not independently
attested. This is a safety guard, not a production sandbox certification.

## CI cost control and full-release gate

Bravon accumulated over 200 verification workflow runs during development. To
reduce GitHub Actions usage on this private repository:

- Every ordinary pull-request update runs the full Python test suite on **3.12**
  plus the Chromium browser smoke suite, and automatically cancels superseded
  pull-request runs.
- After the final source change and code review, apply the
  **`full-release-check`** PR label. The label triggers the **complete
  3.10/3.12/3.13 matrix, long deterministic benchmarks, model-wire checks,
  and the separate remote contract test** against that same reviewed head.
- Main-branch pushes and an authorized manual verification dispatch retain
  the full matrix. Do not confuse the quick PR check with release approval.
- If GitHub reports job failures with no steps or downloadable logs, check
  the account's Actions usage, budget and billing state before concluding
  tests failed. A missing job log is not a test-pass result.
- Keep the source repository private while investigating account limits;
  do not make it public solely to avoid Actions charges.

**PR #11 is not ready to merge until the explicit full-release-check completes
successfully and the other owner/security gates are satisfied.** No full run,
remote Docker execution or production release is claimed merely by adding
this label-trigger workflow.

## Hardened release changes (October 31, 2026)

- Replaced legacy Nginx 1.28-alpine with official stable
  **NGINX 1.30.6-alpine3.24**, pinned to the Docker Hub multi-platform
  index digest. Upstream published security fixes on October 14.
  The new image still requires an architecture-specific vulnerability
  assessment and actual container pull/build and five-probe qualification.
  See `docs/REMOTE_IMAGE_LOCK.md`.
- Runner execution traps SIGTERM/SIGINT to **attempt** teardown and
  refuse successful receipt generation. Hard SIGKILL, virtual-machine
  loss and GitHub's forced cancellation remain outside that guarantee.
- Cancellation/no-receipt regression tests are added. Extracted critical
  authorization, fault-signature and signal-handler functions were tested
  independently in a local Python 3.13 harness (3 focused tests passed).
  **The full repository suite remains unqualified**, as private GitHub
  Actions jobs still report failures without usable step logs.

These changes do not prove a successful cloud Docker deployment.
Keep the repository authorization variable unset.

## Verification / evidence gates

- Unit tests must reject fake Docker runners, unsupported scenarios, invalid GitHub context, tampered reports, incomplete recoveries and existing output files.
- Cancellation tests must verify SIGTERM/SIGINT handler restoration, refusal of a green receipt and best-effort teardown of known disposable projects after an interrupted start.
- Run `python -m pytest -q tests/test_remote_qualification.py` against the fake local Docker runner. This is a controller test, not physical qualification.
- GitHub CI on the PR verifies the new workflow and Python logic **without dispatching real Docker experiments**.
- A single authorized GitHub Actions run, completed with real Docker and followed by artifact review, is still needed to substantiate any remote-experiment claim.
- Only after that owner review may a read-only sanitized receipt be considered for presentation. Do not call the source `Meta Muse`: the remote qualification uses deterministic rules.

This can remove the dependency on a Mac for **owner-authorized known real Docker tests**. It does *not* make production Vercel capable of running Docker or give anonymous jury visitors live repair authority.
