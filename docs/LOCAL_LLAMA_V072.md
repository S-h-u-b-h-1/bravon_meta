# ProofOps v0.7.2 — Local Llama finalization retry

## Why this patch exists

On the user's Mac, `llama3.1:8b` completed six read-only probes in the synthetic `dns-drift` case. There were eight local-model HTTP requests, and the trial was rejected with `InvalidModelStep: Local Ollama generation hit its token limit`. That request count strongly suggests the failure was the *final explanation* step after a successful final-action choice. It does **not** prove the model's conclusion was correct, since the final response was rejected.

In v0.7.1 the final explanation was limited to 384 output tokens while receiving a redundant copy of the entire wire contract. v0.7.2 sends only the selected proposal and recorded evidence. The primary completion requests a small JSON-schema response with a 512-token bound and brief explanation instructions. If and **only if** that completion exhausts the token budget, the local provider tries **one** final explanation again, using `format: "json"` and a 1024-token bound. This is intentional: schema-constrained decoding can fail to terminate on some model/engine combinations. The fallback is **not** accepted on faith; it is parsed with the existing strict field, action, evidence, and confidence checks.

The trial report adds `token_limit_events` and `format_fallbacks`. Counts indicate how many truncations occurred and whether a JSON-mode fallback response was used. The provider rejects both responses if they hit the limit, the final is malformed, the citations are invented, or the proposed action is unsupported. It never silently substitutes a rule-based result. **Neither provider ever executes a repair.** Model calls remain exclusively local on `127.0.0.1:11434`, without any Meta API key or paid API.

This does not establish that Ollama 0.40.8, Llama 3.1 8B, or the user's Apple Silicon machine has an MLX-specific problem. The token cap alone may explain the result. See the [official Ollama structured output documentation](https://docs.ollama.com/capabilities/structured-outputs) for JSON-schema format support.

## Upgrade existing ProofOps v0.7.1 checkout

Download the patch `proofops-v0.7.1-to-v0.7.2.patch` to Downloads. From the existing project:

```bash
cd ~/Desktop/proofops-v0.3-real-lab
source .venv/bin/activate
patch --dry-run -p1 < ~/Downloads/proofops-v0.7.1-to-v0.7.2.patch
```

If the dry run succeeds:

```bash
patch -p1 < ~/Downloads/proofops-v0.7.1-to-v0.7.2.patch
python -m pip install -e '.[dev]'
python -m pytest -q
```

## Run one synthetic-model trial

Check that Ollama runs; do not inject another Docker fault:

```bash
curl -fsS http://127.0.0.1:11434/api/tags > /dev/null
python -u -m proofops.model_protocol local-llama \
  --model llama3.1:8b \
  --family dns-drift \
  --output reports/ollama-dns-v072.json
```

View the actionable, nonsecret fields:

```bash
python - <<'PY'
import json
r = json.load(open('reports/ollama-dns-v072.json'))
for field in ('predicted_action', 'expected_action', 'correct', 'unsafe',
              'tool_calls', 'provider_requests', 'token_limit_events',
              'format_fallbacks', 'error', 'error_detail', 'repair_executed'):
    print(f'{field}: {r.get(field)}')
PY
```

**Acceptance:** `predicted_action=restore_dns`, `correct=True`, and `repair_executed=False` after relevant probes. An invalid or wrong final action remains a failed trial even if all transport and shape checks pass. An `invalid` action with `unsafe=False` means fail-closed, **not** an accurate diagnosis.

## Validation performed when preparing the patch

- Updated Python tests cover a successful local-JSON fallback following a token-limited final, a second token-limit that fails closed, and fabricated evidence rejected after fallback.
- Existing deterministic offline model-contract replay and Docker mock tests remain unchanged.
- **Live Ollama inference was not available in the build environment; new model accuracy is unverified.** No ChatGPT Work or external model API was used.
