#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pytest -q
python3 -m proofops.benchmark --repeats 10
if command -v node >/dev/null 2>&1; then node --check web/app.js; fi
