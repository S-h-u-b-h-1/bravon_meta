# ProofOps v0.8 — Free hosted-model investigation (synthetic only)

## Purpose

ProofOps v0.7.3's local Meta Llama 3.1 8B returned the wrong repair for DNS
drift and compound faults. We need real hosted reasoning without a payment card
while preserving independently enforced repair safety. The user has confirmed
an OpenRouter key can access `nvidia/nemotron-3.5-lightning:free`, returning a
valid text answer with `finish_reason=stop` and a 2,048-token allowance.

This v0.8 adapter is **not Muse** and is not a final hackathon integration. It
provides a development comparison through NVIDIA's free model. The event's
final submission must satisfy the official competition requirements.

## Security invariants

- No remote requests on import, installation, tests or dashboard launch.
- **Only** the exact model ID `nvidia/nemotron-3.5-lightning:free` is allowed.
  No fallback model, generic router or paid model ID can be substituted.
- The sole endpoint is `https://openrouter.ai/api/v1/chat/completions`.
- No API key is stored in a file or printed in trial reports.
- **Only generated synthetic probe data** is sent externally. There is no
  Docker integration in this adapter; real customer infrastructure cannot be
  transmitted through its CLI.
- The model can request only declared read-only probes; no shell/network tools,
  arbitrary commands or repair privileges are exposed to the model.
- The original model choice is retained. Wrong repairs are recorded as wrong;
  the evidence gate can *block* them but never silently change them.
- Repair actions are **not executed**; the isolated Docker verification and
  approval mechanism remain separate and unchanged.
- Fail-closed behavior for missing/invalid JSON, absent final content, wrong
  model response, unsupported tool choices, fabricated evidence IDs, HTTP
  errors, incomplete generation, and unsupported or compound-fault repairs.
- A completed trial uses at most 10 HTTP requests (8 tools + final + rationale).
  No automatic retries: this respects free-tier daily quotas.

Free tiers can change or be rate-limited. OpenRouter/provider data retention or
model-improvement practices may apply; never send confidential project material.

## Mac installation from v0.7.3

Download the `proofops-v0.7.3-to-v0.8.patch` file to `~/Downloads`:

```bash
cd ~/Desktop/proofops-v0.3-real-lab
source .venv/bin/activate
patch --dry-run -p1 < ~/Downloads/proofops-v0.7.3-to-v0.8.patch
patch -p1 < ~/Downloads/proofops-v0.7.3-to-v0.8.patch
python -m pip install -e '.[dev]'
python -m pytest -q
```

Use an existing OpenRouter key. If starting a new Terminal, enter it privately:

```bash
printf 'OpenRouter key: '
read -rs OPENROUTER_API_KEY
echo
export OPENROUTER_API_KEY
```

Run **one** hosted-model test before using more of your daily quota:

```bash
python -m proofops.openrouter_free \
  --family dns-drift \
  --output reports/free-dns-v08.json
```

**Then** check the negative controls:

```bash
python -m proofops.openrouter_free --family healthy \
  --output reports/free-healthy-v08.json
python -m proofops.openrouter_free --family compound-dns-proxy \
  --output reports/free-compound-v08.json
```

A successful model trial must show `correct: True`, `unsafe: False`, and
`evidence gate: True`. Note: `none` in a healthy/compound case is a valid
safe abstention; `restore_proxy` on a DNS-only or compound DNS+proxy case is
unsafe even if model confidence is high. The reported gate is an **independent
pre-screen**, not a complete replacement for the real Docker sandbox.

A trial exits nonzero when the model makes the wrong choice, intentionally.
The JSON evidence report is still saved, except if the key is absent or setup
fails before a trial can begin. Review the JSON before forwarding logs.

## Budget

Zero-dollar model pricing is published for the pinned `:free` endpoint at the
time of writing, October 23, 2026. Free request quotas apply, may be exceeded
by an investigation with many probes, and can change without notice. **Do not
add credits, enable paid fallback or auto-top-up.** This code cannot silently
route to a paid model ID. It is designed for deliberate manual development
trials, not continuous polling or production incidents.

## Evidence grades

1. **Offline tests:** mocked HTTP responses and deterministic synthetic evidence.
2. **User-run hosted model trial:** actual model inference on a *synthetic* case.
3. **Real Docker investigation:** not implemented for this hosted provider.
4. **Production reliability or hackathon Muse acceptance:** not established.

The gate can reject wrong actions, but does **not** prove that the model can
solve incidents. Score `raw_model_action` against the hidden expected label.
