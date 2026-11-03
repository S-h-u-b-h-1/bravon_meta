# Meta Muse evidence bridge — private offline jury receipt

## Purpose

This is the **official Meta Muse System A → Immortality System B** evidence bridge.
It supplements the public Proof Journey's separately recorded local Llama repair examples.
**Do not call those examples official Muse.**

The public /muse page works without Docker or an API key. It displays a
clearly labeled, repository-documented summary of the previous experiment.
An operator can optionally select a privacy-minimized local receipt to display
recorded counts, evidence gate, recovery and transferred-policy outcomes.

## Create a receipt on the owner's Mac

Prerequisites: the previously saved real System A recovered incident and
real System B transfer reports; the Python project environment installed.
The receipt operation is **offline only**: no Docker, Meta inference or network.

From the repository root:

    source .venv/bin/activate

    python -m proofops.jury_receipt \
      --source-report "$HOME/Documents/Bravon-evidence/hosted-muse-active-recovery-20261028T142236Z-after.json" \
      --investigation-report "$HOME/Documents/Bravon-evidence/hosted-muse-dns-drift-v1.json" \
      --transfer-report "$HOME/Documents/Bravon-evidence/antibody-real-transfer-v2.json" \
      --output "$HOME/Documents/Bravon-evidence/jury-muse-receipt-v1.json"

The output must be a **new** private filename in an existing normal directory.
The command rejects symlinks, oversize/invalid inputs, simulated reports,
incorrect model provenance, insufficient independent evidence and incomplete
source-to-transfer auditing. No output is written on refusal.

Open the preview's /muse route (or production only after separate release approval).
Select **Choose local receipt**, then the newly saved jury-muse-receipt-v1.json.
The browser reads it locally; it never uploads it.

## Contents and privacy boundaries

The fixed schema bravon.jury-muse-receipt.v1 contains:
- Official model identity, DNS-drift scenario and restore-DNS action.
- Hosted request count, read-only evidence item count and citation count.
- Accepted gate, 5/5 sandbox record and approved recovery record.
- Fixed DNS safety policy, System B BLOCK/ALLOW candidate decisions and exact
  dangerous and legitimate health-check outcomes.
- Boolean active destination preservation and cleanup flags.
- Linked source/transfer controller content digests and a receipt content digest.
- Non-removable, explicit prototype limitations.

The receipt **does not copy** source or destination IPs, hostnames, private
paths, prompt text, model completions, Docker logs, user identifiers,
credentials, secrets or arbitrary raw report fields.

The browser accepts the exact narrow schema, file-size limit, fixed expected
values and SHA-256 content digest. All values use textContent, never inserted
into executable HTML. There are no POST requests, local storage, API calls
or Docker actions.

## What it does not prove

1. A receipt digest detects accidental/unauthorized changes **relative to the
   receipt**, but it is not a third-party signature; a malicious operator
   can create a different self-consistent file.
2. The offline auditor establishes internal consistency of stored controller
   reports, not independently attested Meta or physical Docker execution.
3. The experiment covers one DNS invariant and two deterministic candidates,
   not universal immunity or production safety.
4. Export does **not** approve publication. Keep all private source, transfer
   and receipt artifacts on the operator's device unless separately cleared
   for sharing, after privacy/security review.

## Jury presentation path

1. The Proof Journey at /#tour compares the separately recorded local Llama
   verified and false-green decisions.
2. The /muse page identifies the distinct documented official hosted Meta Muse
   experiment and its read-only evidence-to-repair boundaries.
3. Optionally load the offline audited receipt locally and disclose that its
   origin is controller-reported, not externally attested.
4. Continue into /assets/immortality.html, showing System B's harmful change
   BLOCK and legitimate-control ALLOW outcomes. The existing Immortality viewer
   can separately inspect a private local transfer candidate.
5. Finish with limitations. No jury member needs Docker, credentials or a
   live paid model call to follow the recorded story.

See docs/IMMORTALITY.md and docs/HACKATHON_DEMO_SCRIPT_3_MIN.md for detailed
physical-experiment procedure and exact source-of-work disclosures.
