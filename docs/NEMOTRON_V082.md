# ProofOps v0.8.2 — Free Nemotron finalization fix

## What happened

A previous live run of the three-case scorecard ended as a partial run in the
first `dns-drift` scenario. Nemotron used reasoning tokens and hit the
`max_tokens` budget before providing a valid tool selection.

## What changed

- Each free inference request **asks** OpenRouter for `reasoning: {"enabled": false}`.
  NVIDIA documents a non-thinking mode, but we have **not** confirmed that
  OpenRouter's free endpoint honors this request. The report identifies this
  as *requested*, never verified.
- 4,096 maximum completion tokens per request instead of 2,048, leaving room
  for a response if reasoning control is ignored.
- Token counts are recorded even when generation is truncated. The report also
  records `finish_reasons`, `request_phases`, and `token_limit_events`.
- Still pinned to `nvidia/nemotron-3.5-lightning:free`; no paid fallback or
  random model routing. Only **synthetic, public** observations are transmitted.
- Same strict JSON parsing, allowlisted tools, evidence gate, approvals, and
  no-repair policy. No failed model decision is converted into success.

## Run on Mac

In an existing ProofOps v0.8.1 checkout, apply the `v0.8.1-to-v0.8.2` patch,
install in your virtualenv and run `pytest -q`.

Verify your `OPENROUTER_API_KEY` is present without displaying it:

```bash
python -c 'import os; print(bool(os.getenv("OPENROUTER_API_KEY")))'
```

First run **one** live synthetic trial instead of the full suite:

```bash
python -u -m proofops.openrouter_free \
  --family dns-drift \
  --output reports/free-dns-v082.json
```

Inspect without further API usage:

```bash
python - <<'PY'
import json
r=json.load(open('reports/free-dns-v082.json'))
for field in ('raw_model_action', 'correct', 'tool_calls', 'model_calls',
              'finish_reasons', 'request_phases', 'reasoning_disabled_requested',
              'token_limit_events', 'completion_tokens', 'reasoning_tokens',
              'error', 'error_detail'):
    print(field, ':', r.get(field))
PY
```

If the first trial works, use the same three-case scorecard:

```bash
python -u -m proofops.model_trials run --confirm 'RUN THREE FREE MODEL TRIALS'
open reports/model-trials-v081.html
```

### Interpretation

- `raw_model_action: restore_dns`, `correct: true`, gate allowed: success for
  this *synthetic* case only.
- `length` in `finish_reasons` and `token_limit_events: 1`: provider still
  exhausted its completion budget. Inspect reasoning token count; don't
  present it as model accuracy.
- `raw_model_action: restore_proxy` or `none`: valid but wrong decision; do
  not override it. The evidence gate still protects execution.
- `HTTP 429`: free quota issue; no paid fallback.

No model access to live Docker. Local validation is not a proof of live model
reliability. API request data may be logged by the free provider; don't send
private configs or personal information.
