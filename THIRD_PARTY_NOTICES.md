# Third-party notices

This file records the third-party software and model used by the Bravon
hackathon build. Bravon does not vendor their source code or model weights.

## Direct Python dependencies

| Component | Declared range | Audited version | License |
| --- | --- | --- | --- |
| FastAPI | `>=0.110,<1` | 0.162.0 | MIT |
| Uvicorn | `>=0.28,<1` | 0.54.0 | BSD-3-Clause |
| Pydantic | `>=2,<3` | 2.14.2 | MIT |
| pytest (development) | `>=8,<10` | 9.2.0 | MIT |
| HTTPX (development) | `>=0.27,<1` | 0.28.1 | BSD-3-Clause |
| OpenAI Python client (optional) | `>=1.70,<3` | 2.54.0 | Apache-2.0 |

The audited versions are the versions installed for the October 31, 2026
release review. Their package metadata and upstream repositories are the
authoritative license sources. MIT, BSD-3-Clause and Apache-2.0 permit the
repository's MIT distribution when their notices and terms are retained.

## Model and local runtime

- Meta Llama 3.1 8B model weights are not stored or redistributed in this
  repository. They are governed by the Meta Llama 3.1 Community License and
  Acceptable Use Policy published with `meta-llama/llama-models`.
- Ollama is an optional local runtime and is not bundled. Its upstream project
  is MIT licensed.
- Recorded hackathon inference used the locally installed `llama3.1:8b`
  model. A separate operator-reported official Meta Muse Spark 1.3 API trial
  is disclosed in the submission materials; its private controller evidence
  is not distributed in this repository and is not third-party attestation.

## Execution image and product assets

- The isolated verifier pulls the official digest-pinned `python:3.12-alpine`
  container image at execution time; the image is not redistributed here.
- The hackathon dashboard HTML, CSS, JavaScript, inline icon, and fixtures are
  first-party repository assets. It loads no third-party font, script, image,
  or analytics service.

## Bravon repository license

Bravon's first-party source is distributed under the MIT License in `LICENSE`.
That license does not replace the separate terms governing Meta model weights,
container images, Python dependencies or other third-party components.
