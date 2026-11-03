#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  printf '%s\n' 'No .venv; run python3 -m venv .venv && .venv/bin/pip install -e ".[dev,meta]"' >&2
  exit 2
fi
exec .venv/bin/python -m proofops.frontier_eval --live --check --models muse-spark-1.3,muse-wonder-1.0
