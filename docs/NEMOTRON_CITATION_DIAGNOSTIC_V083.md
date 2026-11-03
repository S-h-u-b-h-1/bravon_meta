# ProofOps v0.8.3 — citation diagnostic hotfix

This patch applies **on top of** the v0.8.3 format hotfix. The package
version remains 0.8.3. It makes **no changes** to the independent evidence
gate or the Docker repair engine.

## Why

A real free Nemotron run proposed `restore_dns` after five read-only probes,
with no format errors. The evidence gate rejected it. For this synthetic DNS
fixture, the action is offered only when required probes exist. Missing model
citations are the most likely cause, but the original local report's exact
gate reason should be checked before attributing causality definitively.

## Changes

- Final explanation prompts include the **exact required evidence IDs** drawn
  from actual observations already made. The model still produces its own
  final citation list. The adapter does **not fill, correct, or retry** it.
- Synthetic trial JSON adds `evidence_gap`: observed, cited, required, missing
  probes, and missing model citations. It is diagnostic only.
- CLI prints evidence gate reason and missing probe/citation IDs.
- HTML scorecard displays missing probe and citation IDs when available.
- No auto-retry, paid fallback, network calls during rendering, Docker repair,
  or alteration to evidence verdicts.

## Check the previous report (zero API calls)

```sh
cd ~/Desktop/proofops-v0.3-real-lab
source .venv/bin/activate
python - <<'PY'
import json
from pathlib import Path
r = json.loads(Path('reports/free-dns-format-hotfix.json').read_text())
print('Action:', r['raw_model_action'])
print('Gate reason:', r['evidence_gate']['reason'])
print('Observed:', [x['evidence']['evidence_id'] for x in r['trace'] if x['kind']=='tool'])
print('Cited:', next((x['evidence_ids'] for x in r['trace'] if x['kind']=='proposal'), []))
PY
```

## After applying the patch

```sh
python -m pytest -q
python -u -m proofops.openrouter_free --family dns-drift \
  --output reports/free-dns-citation-test.json
python -m proofops.model_trials render reports/free-dns-citation-test.json \
  --output reports/model-trials-citation-test.json
open reports/model-trials-citation-test.html
```

The hosted trial uses free-tier requests (quota limited), sends only generated
synthetic fixtures, and cannot repair real services.
