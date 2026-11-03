# ProofOps v0.7.1 — Constrained local Meta Llama adapter

## What the first real Llama result established

The Mac's `llama3.1:8b` download succeeded. The first opt-in local trial reported `InvalidModelStep`, no read-only probes, no repair. This is a *failed model trial*, not a verified API call to Muse or an AI accuracy success.

## Why this patch exists

v0.7 sent Ollama `format: "json"` and then expected one of two strict JSON shapes (tool or final). JSON mode limits syntax but does not enforce those two application-specific shapes. v0.7 also recorded only the exception type, hiding the reason for the rejection.

v0.7.1 uses two bounded, schema-constrained local HTTP requests **when finalizing**: first an enumerated choice of the next read-only probe or proposed action, and then—only when a final action is selected—a separate evidence-grounded explanation schema. Tool choices require just one HTTP request. This avoids complex `oneOf` schemas and lets the existing exact `parse_step` and independent evidence checks remain authoritative.

The read-only tool names, evidence IDs, and permitted repairs remain unchanged. The model does not get a shell, credentials, remote HTTP endpoints, or permission to execute repairs. It can choose `final_none` when it cannot justify any repair. The local endpoint stays `127.0.0.1:11434`, redirects are rejected, and model-generated response text is **not** included in error messages.

The report now includes `error_detail` and `provider_requests`. These are for troubleshooting; the report still explicitly marks synthetic evidence and does not claim the repair was executed.

## Upgrade existing v0.7 checkout

Stop any ProofOps web server first. From Terminal:

```bash
cd ~/Desktop/proofops-v0.3-real-lab
source .venv/bin/activate
patch --dry-run -p1 < ~/Downloads/proofops-v0.7-to-v0.7.1.patch
```

Only if the dry run succeeds:

```bash
patch -p1 < ~/Downloads/proofops-v0.7-to-v0.7.1.patch
python -m pip install -e '.[dev]'
python -m pytest -q
```

Ensure the Ollama service is running (`curl -fsS http://127.0.0.1:11434/api/tags`), then run one **synthetic** live-model trial:

```bash
python -u -m proofops.model_protocol local-llama \
  --model llama3.1:8b \
  --family dns-drift \
  --output reports/ollama-dns-v071.json
```

Then inspect the result **without printing raw model output**:

```bash
python - <<'PY'
import json
from pathlib import Path
p = Path('reports/ollama-dns-v071.json')
r = json.loads(p.read_text())
for field in ('predicted_action', 'expected_action', 'correct', 'unsafe',
              'tool_calls', 'provider_requests', 'error', 'error_detail'):
    print(field + ':', r.get(field))
PY
```

If the model completes the tool loop on DNS, repeat with `--family proxy-misroute`, `--family backend-outage`, `--family healthy`, and `--family compound-dns-proxy`. If it fails, save the report and the new `error_detail`; do not assume local Llama can reliably drive the product. This model is Llama 3.1 8B, **not** Muse Spark 1.3.

**Known limits:** The patch was tested against mocked Ollama HTTP responses, not a live local Llama on the author's machine. JSON schema constraints improve compliance, not correctness. Wrong final actions or unsupported citations still fail verification, and no benchmark should report local model correctness based on mocked results. The binary Ollama installation and 4.9 GB model are only present on the user's Mac.
