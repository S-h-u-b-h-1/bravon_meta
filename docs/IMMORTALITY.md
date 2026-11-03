# Bravon Immortality — Nightmare & Antibody Engine

**Hackathon-period prototype, 28 October 2026.** This is a falsifiable,
two-system engineering demonstration. It is **not** a global immune network,
autonomous counterexample discovery, production incident prevention, external
attestation, or a claim of invention/novelty.

## What is genuinely new in this branch

- Compiles one of **three fixed, non-executable invariants** only after a
  previously recorded official Meta Muse Spark 1.3 investigation has a valid
  original action, cited evidence, independent sandbox verification and
  explicitly approved active recovery proof.
- Exports a portable policy with only rule family, model identity and linked
  controller proof digests. It exports **no source IP, machine path, source
  file, raw model response, API key, Docker socket, or user data**.
- Evaluates the policy against a **different declared topology**. Safe and
  harmful changes are both exercised to measure overblocking and missed
  dangerous configurations.
- Creates deterministic bounded "nightmares" rather than model-generated shell
  commands. It handles DNS, proxy-target and backend-health policies offline.
- An opt-in real-Docker test isolates **System B** on a different subnet and
  stages one dangerous DNS change **only inside B's own temporary clone**. It
  also tests a legitimate alternate-backend route and checks that the active
  destination never changed or failed. New Compose projects are torn down.
- A read-only browser page can open the resulting PRIVATE report locally.
  Selecting a report does not upload it or call Meta.

## Pre-existing foundation and disclosure

The frozen pre-hackathon cutoff is tag
  hackathon-start-baseline-2026-10-26
at commit b0dd80f721d28d36e9e680bb18181ae20d4d0347.

The original three-fault disposable Docker lab, fixed verification checks,
approval gates, evidence-envelope primitives, and other foundation are
pre-existing. **Do not call those original components hackathon inventions.**
The Immortality policy compiler, cross-topology evaluators, test runner and
browser viewer are new experiments built on that foundation.

## A — Compile an antibody (read-only, no external calls)

From the existing PR #3 descendant branch with Python dependencies installed:

    python -m pytest -q tests/test_immortality.py tests/test_immortality_docker.py

    python -m proofops.immortality compile \
      --source-report "$HOME/Documents/Bravon-evidence/hosted-muse-active-recovery-20261028T142236Z-after.json" \
      --output "$HOME/Documents/Bravon-evidence/dns-antibody-v1.json"

The compiler independently rescans the stored model citation semantics and
requires a complete recovery chain. The local source report is never edited.

## B — Simulate policy transfer to different topology (read-only)

    python -m proofops.immortality preview \
      --source-report "$HOME/Documents/Bravon-evidence/hosted-muse-active-recovery-20261028T142236Z-after.json" \
      --slot 150 \
      --output "$HOME/Documents/Bravon-evidence/antibody-preview-v1.json"

This is explicitly marked SYNTHETIC_POLICY_PREVIEW_ONLY. It compares two
proposed configurations, BLOCK versus ALLOW, but makes **zero Docker or Meta
calls**. This is a useful correctness preview, NOT an observed Docker success.

## C — Real independent System B experiment (separate operator approval)

**Preflight:** start Docker Desktop and require `docker info` to report
server details. The new CLI refuses a disconnected Docker daemon **before**
creating a new evidence report or any temporary Docker project. The separate
hackathon worker tests also require the pinned image referenced in
`proofops/hackathon_worker.py`; pull that exact image only with Docker running.
If an earlier transfer attempt failed, preserve that JSON and use a new output
name rather than overwriting it.


The following command intentionally creates **new disposable** Docker Compose
stacks on the private 10.223.150.0/24 and 10.223.151.0/24 networks. It changes
only a temporary B verification clone, not the old System A or System B's
healthy active services. It may pull/build container images and use local
resources. Don't run until the operator explicitly authorizes this test,
Docker Desktop is healthy, and the subnets do not overlap other networks.

    python -m proofops.immortality_docker \
      --source-report "$HOME/Documents/Bravon-evidence/hosted-muse-active-recovery-20261028T142236Z-after.json" \
      --slot 150 \
      --output "$HOME/Documents/Bravon-evidence/antibody-real-transfer-v1.json" \
      --confirm 'RUN ISOLATED ANTIBODY LAB'

This runner:
1. Rechecks the source recovery proof and requires the DNA-rule family.
2. Creates fresh isolated System B with healthy CoreDNS/Nginx/backends.
3. Uses B's own gateway, backend and wrong-target IPs (not System A's).
4. Blocks the proposed dangerous DNS target before deployment.
5. Reproduces its failure only in the disposable clone: dns-record and e2e
   fail, proving an actual would-be customer impact in the controlled fixture.
6. Starts another fresh clone; allows a legitimate route to a healthy standby
   while preserving B's DNS, and checks 5/5 pass.
7. Checks the *active B stack* retained 5/5 health and its fingerprint while
   both experiments ran. Removes only the two newly generated Compose projects.
8. Records a private redacted JSON report, including mode, decisions, check
   IDs/pass flags, source proof digests, cleanup, and its own content hash.

If any stage fails, report FAILED and **do not** claim prevention. The runner
attempts to clean the known new Docker stacks. If cleanup fails, it preserves
the private run directory for operator inspection. There are no automatic
retries, model calls, privileged production endpoints, or remote customer
infrastructure access.

## D — View locally, never upload

Open https://bravon-meta.vercel.app/assets/immortality.html only **after**
the reviewed feature is merged/deployed (until then, use the Vercel PR preview
or serve the page locally). Click "Choose local JSON report". The browser
uses the File API and textContent to avoid uploading or executing report data.
The built-in example is explicitly labeled SYNTHETIC, not a real Meta result.
The viewer does not authenticate the provenance of the uploaded JSON.

## Measurable acceptance criteria

- Source diagnosis and gate valid; verified sandbox/active recovery digest chain.
- Source and destination networks genuinely different; no source IP in policy.
- BLOCK dangerous target; ALLOW safe alternate-backend control.
- Clone reproduces exactly the DNS and E2E failures for the dangerous case.
- Clone control remains 5/5 green while alternate routing is exercised.
- Active destination remains 5/5 healthy and unchanged; known projects removed.
- Invalid source, missing citation, stale/corrupt proof, tampered policy,
  invalid IPs, unknown rule and unsupported action all fail closed.
- CI fake-Docker tests **do not establish actual Meta accuracy** or physical
  Docker qualification on the user's Mac. Keep results properly labeled.

## Boundaries

No transfer to untrusted external machines, cryptographic origin attestation,
gossip network, global vulnerability database or cross-customer data exchange.
Policy digestion checks internal consistency, **not** authenticity. A good
policy result verifies exactly one invariant; all other system hazards may
still exist. Physical DNS transfer is the first supported end-to-end
experiment. Proxy/back-end policies are pure offline checks until extended
physical verification is independently demonstrated.

The event requires clear disclosure of work built during the hackathon,
public source only after security/author approval, and a short truthful demo.
Keep repository private and all external uploads/paid Meta calls disabled
until separately approved.


## E — Independently cross-check the operator-saved System B JSON

After one real B run reports success, **do not rely only on the Terminal
summary**. Run the new *read-only* auditor against both saved records:

    python -m proofops.immortality_audit \
      --source-report "$HOME/Documents/Bravon-evidence/hosted-muse-active-recovery-20261028T142236Z-after.json" \
      --transfer-report "$HOME/Documents/Bravon-evidence/antibody-real-transfer-v2.json"

It recomputes the original recovery-to-antibody binding, original Meta-cited
evidence gate, sandbox/active recovery content digests, destination network
difference, source policy digest, System B transfer content digest and both
exact five-probe before/after patterns. It rejects missing or extra fields,
wrong check identities, missing control, false-green results, forged labels,
and simulated Docker output offered as a real-world result.

This **only validates consistency of stored, operator-controlled reports**.
It cannot independently attest that Meta, Docker or a particular host actually
performed the recorded work. Retain original private evidence and disclose
that limitation in public claims.

For a schema-checked local candidate file suitable for manual privacy review
and the read-only Immortality browser viewer, pass an *unused new filename*:

    python -m proofops.immortality_audit \
      --source-report "$HOME/Documents/Bravon-evidence/hosted-muse-active-recovery-20261028T142236Z-after.json" \
      --transfer-report "$HOME/Documents/Bravon-evidence/antibody-real-transfer-v2.json" \
      --export "$HOME/Documents/Bravon-evidence/antibody-demo-candidate-v1.json"

The exporter creates a new local file containing only fixed schema fields,
source proof digests, source model/action, destination test slot and boolean
probe outcomes; it never includes full Docker logs, IP addresses, local file
paths, Meta prompts or private credentials. It **does not** upload anything,
change the private GitHub repository, publish an asset or submit the hackathon.
Public release of any evidence still requires separate owner approval and a
final history/privacy audit.
