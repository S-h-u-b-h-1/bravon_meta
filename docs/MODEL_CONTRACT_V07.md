# ProofOps v0.7 — Bounded Model Investigator & Offline Local Llama

**Status (Oct 23, 2026):** Contract code implemented and tested locally. No remote Meta Model API calls, no Work usage, no Docker daemon access in the authoring environment. **Local Llama inference and v0.7 real-Docker integration have not yet been tested on the user's Mac.** The earlier v0.4.1 real-Docker three-scenario qualification is a separate, user-verified achievement.

## Why this milestone exists

v0.6 proved that rule-based investigators can use an evidence-only tool interface. It did **not** demonstrate intelligence from a model: 42/42 was a synthetic fixture regression test. v0.7 deliberately introduces a **JSON wire boundary** between an opaque model/provider and the existing tool loop. A model chooses its next read-only observation, or proposes one allowlisted repair with citations. The executor is still responsible for independently deciding whether the repair is justified. It is never given a model-supplied shell command.

### JSON response contract

The provider must output one unwrapped JSON object, with **exactly** one of two forms.

```json
{"kind":"tool","name":"lookup_dns","arguments":{}}
```

```json
{"kind":"final","action":"restore_dns","root_cause":"DNS points away from the declared edge","explanation":"Customer path fails while gateway and backend are healthy","confidence":0.75,"evidence_ids":["topology","customer-path","dns","gateway","backend-a"]}
```

Tool names: `topology`, `customer_path`, `lookup_dns`, `inspect_gateway`, `probe_backend`. Only `probe_backend` accepts arguments: `{"backend":"backend-a"}` or `{"backend":"backend-b"}`. Final actions: `none`, `restore_dns`, `restore_proxy`, `failover`. The request includes permitted tools, observed evidence, a trust-boundary instruction, and output format; it **does not** contain the fixture name or correct answer.

Unknown tools, fields, malformed JSON, extra tool arguments, nonexistent evidence citations, duplicate evidence citations, repeated already-observed probes, non-finite confidence, or a call budget overrun are rejected before any mutation. Repairs remain gated by the v0.4.1 **independent second Docker stack, explicit approval, revision/fingerprint check and post-apply verification**. Evidence references alone are not proof of a correct repair.

## First run: no model, no Docker, no API

From your existing v0.6 project, after applying the v0.6 → v0.7 patch:

```bash
python -m pytest -q
python -m proofops.model_protocol run --seed 20261023 --cases 42 \
  --output reports/model-wire-v07.json
python -m proofops.model_protocol verify-report reports/model-wire-v07.json
open reports/model-wire-v07.html
```

This runs **a deterministic NON-AI emulator** through the exact provider JSON contract. Its purpose is regression testing and safe parsing, *not* a claimed local Llama accuracy score. It needs no external model, credentials or Docker.

## Optional local Meta Llama: no paid API key

Meta explicitly permits its open-weight models for the hackathon (subject to the final event rules). On your Apple Silicon Mac with 18 GB unified memory, the **quantized `llama3.1:8b` model (4.9 GB download)** is a reasonable first trial. Leave room for macOS, Docker Desktop, and the model runtime; avoid running resource-heavy Docker builds alongside model download/inference. Through Ollama, a model response uses local loopback HTTP rather than Meta's paid Model API. The 4.9 GB is compressed model size, **not** a guarantee of total peak RAM usage.

Get Ollama from <https://ollama.com/download/mac> (or install with an official package manager), then in Terminal:

```bash
ollama --version
ollama pull llama3.1:8b
ollama list
curl -fsS http://127.0.0.1:11434/api/tags > /tmp/proofops-ollama-tags.json
```

Launch Ollama if it is not already running. On some installations, the Ollama app runs the local service automatically; do not run a second `ollama serve` against an occupied port.

### Synthetic single-case *actual local model* test

After `ollama pull`, run **explicitly**:

```bash
cd ~/Desktop/proofops-v0.3-real-lab
source .venv/bin/activate
python -u -m proofops.model_protocol local-llama \
  --model llama3.1:8b --family dns-drift \
  --output reports/ollama-dns-v07.json
```

This now **does invoke a real local Meta Llama** (no cloud API). Inspect `predicted_action`, `correct`, `unsafe`, `tool_calls` and the trace. An 8B model may return malformed JSON or make mistakes; such cases are scored as `invalid`/incorrect or unsafe as appropriate. A single successful case is not evidence of generalization. Repeat with `--family proxy-misroute`, `backend-outage`, `healthy`, `primary-no-standby`, `compound-dns-proxy`, and `spoofed-text`; report both errors and successes.

No inference occurs unless `local-llama` is explicitly selected. This adapter has a fixed loopback-only endpoint (`127.0.0.1:11434`) and refuses redirects. It never loads `MODEL_API_KEY` or charges any cloud account. Network access is required once to download the model.

### Optional controlled real-Docker model-driven investigation

**Only** once synthetic behavior looks safe, confirm your disposable lab is in the intended state. Your most recent shared status was `dns-drift`, `diagnosed`, with a prior read-only proposal. You **do not** need to inject it again. To re-analyze that existing incident using the locally hosted Llama:

```bash
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
python -m proofops.real_lab status
python -u -m proofops.real_lab investigate \
  --investigator ollama-local --local-model llama3.1:8b \
  > /tmp/proofops-v07-real-ollama.json
```

`--investigator wire-emulator` provides a zero-inference diagnostic smoke test of the same JSON path on the existing active incident.

**Investigate does not execute a repair.** Even if the model recommends a wrong action, only a separately approved, independently verified repair can affect the target lab. Do not use these experiments on non-disposable infrastructure.

After inspection, either use the existing sandbox-verify + approval workflow or intentionally reset the **disposable** lab (`python -m proofops.real_lab reset`). Do not inject a second fault while an incident is active.

## What this milestone DOES NOT establish

- **No live Muse testing.** `llama3.1:8b` is Meta's open-weight Llama, **not** Muse Spark/Wonder. Muse credentials/credits remain unresolved.
- **No v0.7 live-Docker validation from the authoring environment.** The Docker tests use a fake Compose runner; your Mac must qualify it.
- **No novel-fault benchmark yet.** The 14 seeded cases are public synthetic development scenarios. A different seed changes ordering and IPs, not underlying fault families.
- **No protection against a malicious locally installed Ollama runtime** or arbitrarily modified Python/Docker source. The program trusts the local operator and is not suitable for hosting publicly.
- A SHA-256 digest and local report replay are **not signatures** or externally witnessed attestations.

## Proposed next acceptance gate

1. All local Python tests pass.
2. Offline deterministic wire evaluation passes report replay.
3. An actual local Llama successfully chooses read-only probes and produces a valid evidence-backed proposal on DNS (record its failures honestly).
4. Repeat at least seven cases including ambiguous faults, prompt-injection text, and healthy/no-op.
5. In disposable Docker, test one Llama proposal; independent replica verification must block a wrong or unsupported fix and preserve the original stack.
6. Only then consider integrating live Muse, once official credits are active, to compare Llama and Muse under the same interface.

This is a **pre-hackathon preparation prototype**; confirm the published rules on October 26 before including pre-event code in any contest submission.

## v0.7.1 follow-up

The first local Llama 3.1 8B trial completed without reading any tools and returned `InvalidModelStep`, which is a failed inference evaluation. v0.7.1 constrains the Ollama output schema and adds a compact error reason. See [LOCAL_LLAMA_V071.md](LOCAL_LLAMA_V071.md). The base v0.7 wire contract and repair gates are unchanged.
