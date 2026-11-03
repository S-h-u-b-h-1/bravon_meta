#!/usr/bin/env bash
# Default simulation stays localhost-only. Opt-in Docker UI with PROOFOPS_ENABLE_DOCKER_UI=1.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then python3 -m venv .venv; fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -e '.[dev]'
PORT="${PROOFOPS_PORT:-8000}"
if ! [[ "$PORT" =~ ^[0-9]{2,5}$ ]] || [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ]; then
  echo "PROOFOPS_PORT must be an unprivileged TCP port (1024..65535)" >&2
  exit 2
fi
printf '\nProofOps simulation: http://127.0.0.1:%s\nProofOps Docker lab: http://127.0.0.1:%s/docker\nDocker controls: %s\nCtrl+C to stop.\n\n' \
  "$PORT" "$PORT" "${PROOFOPS_ENABLE_DOCKER_UI:-0}"
exec python -m uvicorn proofops.api:app --host 127.0.0.1 --port "$PORT"
