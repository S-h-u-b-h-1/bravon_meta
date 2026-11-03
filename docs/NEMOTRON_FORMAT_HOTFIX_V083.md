# ProofOps v0.8.3 — safe free-Nemotron formatting hotfix

This is a small compatibility patch to **v0.8.3**, not a new milestone. The
installed package version intentionally stays `0.8.3`.

## What we actually observed on the user's Mac

The one-request inspector returned `{"choice":"topology"}` with seven output
tokens, `finish_reason=stop`, and zero reasoning tokens. This proves the free
provider can return the existing response contract. An earlier run returned a
non-JSON response with only three output tokens. That response's actual text
was not captured, so its content is **unknown**.

## What changes

- When selecting the next read-only probe, accept a **whole, exact, currently
  offered choice name** such as `topology`, or a JSON string `"topology"`, in
  addition to the canonical JSON object `{"choice":"topology"}`.
- Reject prose, multiple choice names, unknown names, partial JSON, and any
  extra output. **Final repair explanations still require strict JSON**.
- Count `compact_choice_recoveries` in reports. For other malformed responses,
  record at most three short, redacted previews so the next failure can be
  diagnosed with evidence. All report HTML escapes untrusted content.
- No automatic retries, model switching, additional API calls, Docker actions,
  approval bypass, or change to the independent evidence gate.

## Test it yourself (Mac)

From your existing ProofOps directory:

```sh
source .venv/bin/activate
python -m pytest -q
python -u -m proofops.openrouter_free --family dns-drift \
  --output reports/free-dns-v083-format-test.json
python -m proofops.model_trials render reports/free-dns-v083-format-test.json \
  --output reports/model-trials-format-test.json
open reports/model-trials-format-test.html
```

The live test only transmits public synthetic incident data to the pinned
`:free` OpenRouter endpoint. It uses free-tier requests (subject to quotas)
and makes no Docker changes. Check `raw_model_action`, `evidence_gate.allowed`,
`compact_choice_recoveries`, `invalid_reply_previews`, and `error_detail`.
An exact-choice fallback **might** help the earlier three-token failure, but
we cannot claim that without seeing that original reply.
