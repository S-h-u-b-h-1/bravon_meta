# ProofOps v0.8.3: evidence-aware proposal availability

**What the user's v0.8.2 experiment established:** The hosted free model correctly chose `restore_dns` after only three read-only probes. The independent gate rejected that correct *action* because gateway and selected-backend health were not observed. This is a correct safety rejection, not full model qualification.

## What changed

The OpenRouter adapter offers `final_none` at every turn, but only offers a non-abstention final action after collecting enough probe identities for that action:

| Action | Minimum read-only evidence |
| --- | --- |
| `restore_dns` | topology, customer path, DNS, gateway, and health of the backend selected by gateway; if selection unknown, probe both |
| `restore_proxy` | topology, customer path, DNS, gateway, and backend A |
| `failover` | topology, customer path, DNS, gateway, backend A, backend B |
| `none` | always available |

This is a **coverage** check only. It doesn't inspect fixture labels or determine what repair is correct. The independent `assess_proposal` still evaluates whether the observations *support* the selected action. A wrong or unsupported action remains rejected. The model may still abstain too early, which is measured as a missed repair.

The scorecard reports separately: raw correct actions, gate-qualified correct actions, unsafe proposals, gate rejections, and model calls. No Docker services or repairs are touched by hosted-model trials.

## Upgrade and test

```bash
cd ~/Desktop/proofops-v0.3-real-lab
source .venv/bin/activate
patch --batch --forward --dry-run -p1 < ~/Downloads/proofops-v0.8.2-to-v0.8.3.patch
# Only if dry run succeeds:
patch --batch --forward -p1 < ~/Downloads/proofops-v0.8.2-to-v0.8.3.patch
python -m pip install -e '.[dev]'
python -m pytest -q
```

Render the **existing** v0.8.2 report with zero API calls:

```bash
python -m proofops.model_trials render reports/free-dns-v082.json \
  --output reports/model-trials-v083-before.json
open reports/model-trials-v083-before.html
```

If the OpenRouter free quota permits, run **one** new synthetic-only trial:

```bash
python -u -m proofops.openrouter_free --family dns-drift \
  --output reports/free-dns-v083.json
python -m proofops.model_trials render reports/free-dns-v083.json \
  --output reports/model-trials-v083-after.json
open reports/model-trials-v083-after.html
```

Neither step executes a repair. The provider is pinned to the `:free` endpoint with no paid fallback. Never paste credentials into chat.
