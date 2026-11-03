#!/usr/bin/env bash
# Offline development audit. Does NOT start Docker, dispatch Actions or use model APIs.
# Requires an existing Python environment with project dev dependencies and Node 22+.
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$REPO_ROOT"

PYTHON="${BRAVON_AUDIT_PYTHON:-python3}"
NODE="${BRAVON_AUDIT_NODE:-node}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "OFFLINE AUDIT BLOCKED: Python is not installed" >&2
  exit 2
fi
if ! command -v "$NODE" >/dev/null 2>&1; then
  echo "OFFLINE AUDIT BLOCKED: Node is not installed" >&2
  exit 2
fi

echo "[1/6] Parse local Python modules without installing or downloading dependencies"
"$PYTHON" - <<'PY'
import ast
from pathlib import Path

root = Path.cwd()
count = 0
for directory in ("proofops", "tests", "qa"):
    for path in sorted((root / directory).rglob("*.py")):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        count += 1
print(f"Python syntax: {count} local source files parsed")
PY

echo "[2/6] Validate the frontend JavaScript syntax"
for source in web/app.js web/docker.js web/hackathon.js web/proof-journey.js \
              web/remote-evidence.js web/muse-evidence.js web/immortality.js \
              web/route-switcher.js; do
  "$NODE" --check "$source"
done

echo "[3/6] Run read-only frontend/remote evidence behavior tests"
"$NODE" --test \
  tests/test_remote_evidence.cjs \
  tests/test_muse_evidence.cjs \
  tests/test_proof_journey.cjs \
  tests/test_bravon_ui.cjs \
  tests/test_immortality_viewer.cjs \
  tests/test_model_trials_accessibility.cjs

echo "[4/6] Run no-real-Docker Python contract and privacy tests"
"$PYTHON" -m pytest -q \
  tests/test_remote_qualification.py \
  tests/test_http_smoke.py \
  tests/test_frontend_pages.py \
  tests/test_qualification.py \
  tests/test_jury_receipt.py \
  tests/test_immortality_audit.py

echo "[5/6] Confirm remote execution stays disabled and patch format is clean"
"$PYTHON" -m proofops.remote_qualification --scenario dns-drift --plan
if command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
  git diff --check
fi

echo "[6/6] Verify real public-mode HTTP routes, assets, security headers and write denial (loopback only)"
"$PYTHON" qa/http_smoke.py

echo "OFFLINE RELEASE CHECK: PASSED"
echo "Scope: syntax, selected simulated tests and refusal contracts only."
echo "Not tested: physical Docker, hosted Muse, private GitHub Actions, Vercel or third-party attestation."
