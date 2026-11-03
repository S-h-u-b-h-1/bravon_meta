#!/usr/bin/env bash
# No Docker run and no Meta API call: verifies only controller/API contracts.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pytest -q tests/test_real_lab.py
if command -v node >/dev/null 2>&1; then node --check web/docker.js; fi
printf 'Offline controller/API tests completed; real Docker runtime not tested by this script.\n'
