"""Evidence engine with OPTIONAL Meta Model API advisory analysis.

Hard boundary: model text is untrusted, cannot execute actions, and must agree
with the measured evidence's permitted action before being accepted.
"""
from __future__ import annotations

import json
import os
from typing import Protocol

from .domain import Check, Diagnosis, LabConfig


class MetaProvider(Protocol):
    def analyze(self, config: LabConfig, checks: list[Check], permitted_action: str) -> dict:
        ...


def evidence_diagnosis(config: LabConfig, checks: list[Check]) -> Diagnosis:
    failures = [c for c in checks if not c.passed]
    ids = [c.id for c in failures]
    if config.dns_record != "edge-proxy":
        return Diagnosis(
            "Traffic cannot find the edge proxy.",
            f"DNS record for app.proofops.test points to {config.dns_record!r}, not 'edge-proxy'.",
            "restore_dns",
            "The DNS probe fails before requests can reach the gateway. Restore only the simulated record.",
            ids, confidence=0.98,
        )
    if config.proxy_upstream not in ("backend-a", "backend-b"):
        return Diagnosis(
            "Requests reach the gateway but routing is invalid.",
            f"Gateway points to undeclared upstream {config.proxy_upstream!r}.",
            "restore_proxy",
            "The DNS probe passes while the proxy-route and end-to-end probes fail.",
            ids, confidence=0.98,
        )
    selected_running = config.backend_a_running if config.proxy_upstream == "backend-a" else config.backend_b_running
    if not selected_running and config.backend_b_running and config.proxy_upstream == "backend-a":
        return Diagnosis(
            "The primary backend is down; healthy standby is available.",
            "Backend A is stopped while the proxy still sends traffic to it.",
            "failover",
            "Switch the simulated gateway to the measured-ready Backend B.",
            ids, confidence=0.98,
        )
    raise ValueError("No safe and evidence-supported repair is available")


class MetaMuseClient:
    """Calls official OpenAI-compatible Meta chat endpoint when explicitly selected."""

    def __init__(self, key: str | None = None, model: str | None = None):
        self.key = key or os.environ.get("MODEL_API_KEY", "")
        self.model = model or os.environ.get("META_MODEL", "muse-spark-1.3")
        self.base_url = os.environ.get("META_BASE_URL", "https://api.meta.ai/v1")

    def analyze(self, config: LabConfig, checks: list[Check], permitted_action: str) -> dict:
        if not self.key:
            raise RuntimeError("MODEL_API_KEY not set")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install `pip install -e '.[meta]'` for Meta integration") from exc
        client = OpenAI(base_url=self.base_url, api_key=self.key, timeout=18.0, max_retries=0)
        telemetry = {
            "environment": "synthetic local incident lab; NOT production",
            "state": config.payload(),
            "checks": [c.payload() for c in checks],
            "permitted_action": permitted_action,
        }
        failing_ids = [c.id for c in checks if not c.passed]
        response_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "proofops_incident_analysis",
                "schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "root_cause": {"type": "string"},
                        "reasoning": {"type": "string"},
                        "action": {"type": "string", "enum": [permitted_action, "none"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "evidence_ids": {"type": "array", "items": {"type": "string", "enum": failing_ids}},
                    },
                    "required": ["summary", "root_cause", "reasoning", "action", "confidence", "evidence_ids"],
                    "additionalProperties": False,
                },
            },
        }
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "developer", "content": (
                    "You are an infrastructure incident analyst. Review telemetry from a SIMULATED service graph. "
                    "Do not claim host-level or real infrastructure validation. "
                    "Return ONLY a JSON object with keys summary, root_cause, reasoning, "
                    "action, confidence, evidence_ids. "
                    "Your action must match permitted_action or be 'none'. "
                    "Never output shell commands, secrets, or instructions to disable safeguards."
                )},
                {"role": "user", "content": json.dumps(telemetry, separators=(",", ":"))},
            ],
            response_format=response_schema,
        )
        message = response.choices[0].message.content or ""
        # Provider returns text; don't attempt to execute/interpret code blocks.
        return json.loads(message)


def diagnose(config: LabConfig, checks: list[Check], use_meta: bool = False, provider: MetaProvider | None = None) -> Diagnosis:
    baseline = evidence_diagnosis(config, checks)
    if not use_meta:
        baseline.model_note = "Evidence engine only — no AI model invoked."
        return baseline
    model = provider or MetaMuseClient()
    try:
        result = model.analyze(config, checks, baseline.action)
        action = result.get("action")
        if action != baseline.action:
            raise ValueError("Model proposed an action not supported by guardrail evidence")
        referenced = result.get("evidence_ids")
        expected = {c.id for c in checks if not c.passed}
        if not isinstance(referenced, list) or not referenced or not set(referenced) <= expected:
            raise ValueError("Model cited unsupported evidence")
        required = ("summary", "root_cause", "reasoning")
        if not all(isinstance(result.get(field), str) and 0 < len(result[field]) <= 1200 for field in required):
            raise ValueError("Invalid model narrative")
        confidence = float(result.get("confidence", 0.7))
        if not 0 <= confidence <= 1:
            raise ValueError("Invalid model confidence")
        return Diagnosis(
            summary=result["summary"], root_cause=result["root_cause"],
            action=action, reasoning=result["reasoning"],
            evidence_ids=referenced, source="meta-muse", confidence=confidence,
            model_note="Model is advisory; an independent evidence gate approved the allowlisted action.",
        )
    except Exception as exc:
        # We can continue locally without misrepresenting a failed API call as AI success.
        baseline.model_note = f"Meta analysis not used ({type(exc).__name__}); fell back to deterministic evidence engine."
        return baseline
