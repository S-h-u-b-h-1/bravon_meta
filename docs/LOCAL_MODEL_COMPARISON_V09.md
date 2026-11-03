# ProofOps v0.9.0 — Local model comparison (synthetic only)

This opt-in extension broadens the existing local Ollama **synthetic incident evaluator**, without changing the Docker or OpenRouter repair paths. It supports locally installed `qwen3.5:9b` and `qwen3.5:4b` in addition to the original Meta Llama checkpoints. The legacy `local-llama` CLI remains restricted to Meta Llama; use `local-model` for Qwen.

## On your Mac

```bash
cd ~/Desktop/proofops-v0.3-real-lab
source .venv/bin/activate
python -m pytest -q
ollama list
python -u -m proofops.model_protocol local-model \
  --model qwen3.5:9b --family dns-drift --timeout 240 \
  --output reports/local-qwen9b-dns.json
```

The program may exit with code 2 when the prediction is incorrect. This is **not** a command-installation error. The JSON report contains its probe sequence, final raw action, and error status. It never touches Docker or uses a cloud API.

If the 9B run is too slow or consumes too much memory, the smaller installed 4B checkpoint can be tried:

```bash
python -u -m proofops.model_protocol local-model \
  --model qwen3.5:4b --family dns-drift --timeout 240 \
  --output reports/local-qwen4b-dns.json
```

**Safety and interpretation:** This is an unqualified local-model comparison, not a live infrastructure recovery or Meta model evaluation. The report's `correct` flag checks the expected action for a synthetic fixture; it is **not** a substitute for the v0.9 Docker evidence gate. A correct model guess, even with a good explanation, cannot authorize any repair. `qwen3.5` is not a Meta model. We do not enable Qwen in the Docker investigator command.

The adapter still uses Ollama on `127.0.0.1:11434`, a strict per-step JSON schema, the existing tool/action allowlists, no remote requests, and no executable repair commands. Some Ollama/Qwen versions have exhibited structured-output quirks, so failed formatting must remain an invalid model step rather than being silently corrected. The first live result must be measured on the Mac; local unit tests use simulated Ollama responses only.
