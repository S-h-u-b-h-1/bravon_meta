"""Capability-first Meta Model API evaluation over blind, read-only synthetic incidents.

This is NOT real infrastructure, does NOT execute repairs, and makes NO remote
request unless an operator passes --live. Only pass synthetic data to Meta.

Meta API: https://dev.meta.ai/docs/protocols/responses
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

from .domain import LabConfig
from .probes import check_all

DEFAULT_MODEL = "muse-spark-1.3"
SUPPORTED_MODELS = ("muse-spark-1.3", "muse-wonder-1.0")
ACTIONS = ("restore_dns", "restore_proxy", "failover", "none")
PRICE_PER_MTOK = {
    "muse-spark-1.3": (1.25, 4.25),
    "muse-wonder-1.0": (4.0, 20.0),
}
TOOL_NAMES = (
    "inspect_topology", "lookup_dns", "inspect_gateway", "probe_backend", "probe_customer_path",
)
MAX_TOOL_ROUNDS = 5
MAX_TOOL_CALLS = 12

@dataclass(frozen=True)
class Case:
    id: str
    config: LabConfig
    expected: str
    note: str

CASES = (
    Case("dns_drift", LabConfig(dns_record="unknown-target"), "restore_dns", "One DNS fault"),
    Case("proxy_misroute", LabConfig(proxy_upstream="backend-z"), "restore_proxy", "One proxy fault"),
    Case("backend_outage", LabConfig(backend_a_running=False), "failover", "A down, B healthy"),
    Case("healthy", LabConfig(), "none", "No repair necessary"),
    Case("compound_fault", LabConfig(dns_record="unknown-target", proxy_upstream="backend-z"), "none", "No single safe repair"),
    Case("no_standby", LabConfig(backend_a_running=False, backend_b_running=False), "none", "No healthy standby; refuse failover"),
)

# Important: There is no expected action or root cause in prompts or tool specs.
DEVELOPER_PROMPT = """You are ProofOps' experimental infrastructure investigator.
You are inspecting a DISPOSABLE SYNTHETIC service lab, not real infrastructure.
Decide which READ-ONLY probes you need. Do NOT invent test results. You are not
permitted to execute repairs; you can only recommend an action for later review.
Valid recommendations are restore_dns, restore_proxy, failover, none.
A single recommended action must be enough to restore the customer request path.
If multiple independent faults exist, no safe one-step fix exists, the app is
healthy, or evidence is insufficient, recommend none and explain why.
To support a fault claim, cite evidence IDs returned by the tools (not guessed IDs).
After inspection, return ONLY JSON with keys: root_cause, action, explanation,
evidence_ids (string array), confidence (number 0..1). No Markdown.
Never ask for secrets or claim any real repair was performed."""

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function", "name": "inspect_topology",
        "description": "Read known service relationships and declared backend names, not fault state.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function", "name": "lookup_dns",
        "description": "Read the current app hostname target from synthetic DNS.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function", "name": "inspect_gateway",
        "description": "Read gateway's configured backend upstream and gateway readiness.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function", "name": "probe_backend",
        "description": "Test exactly one declared backend for readiness.",
        "parameters": {
            "type": "object", "properties": {"backend": {"type": "string", "enum": ["backend-a", "backend-b"]}},
            "required": ["backend"], "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function", "name": "probe_customer_path",
        "description": "Make a synthetic end-to-end request and return its result without prescribing any fix.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
]

REPORT_SCHEMA: dict[str, Any] = {
    "type": "json_schema", "name": "proofops_capability_report", "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "root_cause": {"type": "string"},
            "action": {"type": "string", "enum": list(ACTIONS)},
            "explanation": {"type": "string"},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["root_cause", "action", "explanation", "evidence_ids", "confidence"],
        "additionalProperties": False,
    },
}

class SafeSyntheticTools:
    """Read-only tools. Expected label isn't accessible to model or tool handlers."""
    def __init__(self, config: LabConfig):
        self._config = config.clone()
        self.observations: list[dict[str, Any]] = []

    def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name not in TOOL_NAMES:
            raise ValueError("Tool is not on the read-only allowlist")
        if not isinstance(args, dict):
            raise ValueError("Tool arguments must be a JSON object")
        if name != "probe_backend" and args:
            raise ValueError("Unexpected tool arguments")
        if name == "probe_backend" and (set(args) != {"backend"} or args["backend"] not in ("backend-a", "backend-b")):
            raise ValueError("Unsupported backend query")

        cfg = self._config
        if name == "inspect_topology":
            result = {"evidence_id": "topology", "public_host": "app.proofops.test",
                      "dns_expected_target": "edge-proxy", "edge": "edge-proxy",
                      "declared_backends": ["backend-a", "backend-b"]}
        elif name == "lookup_dns":
            result = {"evidence_id": "dns", "hostname": "app.proofops.test", "resolved_target": cfg.dns_record}
        elif name == "inspect_gateway":
            result = {"evidence_id": "gateway", "upstream": cfg.proxy_upstream,
                      "declared_upstreams": ["backend-a", "backend-b"]}
        elif name == "probe_backend":
            backend = args["backend"]
            running = cfg.backend_a_running if backend == "backend-a" else cfg.backend_b_running
            result = {"evidence_id": backend, "backend": backend, "ready": running}
        else:
            checks = check_all(cfg)
            customer = next(c for c in checks if c.id == "e2e")
            result = {"evidence_id": "customer-path", "healthy": customer.passed,
                      "response": "HTTP 200" if customer.passed else "HTTP 503 (synthetic)"}
        self.observations.append(result)
        return result

    @property
    def evidence_ids(self) -> set[str]:
        return {p["evidence_id"] for p in self.observations}


def validate_report(obj: dict[str, Any], evidence_ids: set[str]) -> None:
    if not isinstance(obj, dict):
        raise ValueError("Result must be a JSON object")
    if set(obj) != {"root_cause", "action", "explanation", "evidence_ids", "confidence"}:
        raise ValueError("Report keys do not match the schema")
    if obj["action"] not in ACTIONS:
        raise ValueError("Unsupported proposed action")
    if not all(isinstance(obj[key], str) and 1 <= len(obj[key]) <= 1500 for key in ("root_cause", "explanation")):
        raise ValueError("Missing or oversized report narrative")
    references = obj["evidence_ids"]
    if not isinstance(references, list) or any(not isinstance(p, str) for p in references):
        raise ValueError("Evidence list is malformed")
    if not set(references).issubset(evidence_ids):
        raise ValueError("Model cited evidence the tools did not return")
    if obj["action"] != "none" and len(references) < 1:
        raise ValueError("Action proposed without inspected evidence")
    confidence = obj["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ValueError("Confidence is invalid")


def short_error(exc: Exception, secret: str | None = None) -> str:
    """Minimal diagnostic, never print request headers or authorization secrets."""
    typ = type(exc).__name__
    status = getattr(exc, "status_code", None)
    parts = [typ]
    if isinstance(status, int):
        parts.append(f"HTTP {status}")
    param = None
    code = None
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        detail = body.get("error", body)
        if isinstance(detail, dict):
            param = detail.get("param")
            code = detail.get("code")
    if param and re.fullmatch(r"[a-zA-Z0-9_.\[\]-]{1,80}", str(param)):
        parts.append(f"param={param}")
    if code and re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", str(code)):
        parts.append(f"code={code}")
    return ", ".join(parts)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICE_PER_MTOK[model]
    return round((price_in * input_tokens + price_out * output_tokens) / 1_000_000, 6)


def make_client(key: str):
    from openai import OpenAI
    return OpenAI(
        base_url="https://api.meta.ai/v1", api_key=key,
        timeout=75.0, max_retries=0,
    )


def check_api(client: Any, model: str) -> dict[str, Any]:
    """Smallest paid call, confirms this account+model+Responses route actually works."""
    result = client.responses.create(
        model=model, input="Reply with just READY.", max_output_tokens=384,
        store=False,
    )
    return {"model": model, "reachable": bool(getattr(result, "output", None)),
            "received_text": bool(getattr(result, "output_text", ""))}


def investigate_case(client: Any, model: str, case: Case, max_rounds: int = MAX_TOOL_ROUNDS) -> dict[str, Any]:
    """Model picks its own observations and action; NO repair executes."""
    tools = SafeSyntheticTools(case.config)
    created = time.monotonic()
    totals = {"input_tokens": 0, "output_tokens": 0}
    call_count = 0
    rounds = 0
    prev_id: str | None = None
    payload: Any = [
        {"role": "developer", "content": DEVELOPER_PROMPT},
        {"role": "user", "content": (
            "Investigate a report about app.proofops.test. The root cause is UNKNOWN to you. "
            "You may use the available read-only tools. Recommend one safe action if verified, otherwise none."
        )},
    ]
    final: dict[str, Any] | None = None

    while rounds < max_rounds:
        rounds += 1
        kw: dict[str, Any] = {
            "model": model, "input": payload, "tools": TOOL_SCHEMAS,
            "text": {"format": REPORT_SCHEMA}, "max_output_tokens": 4200,
            "store": True, "reasoning": {"effort": "high" if model == "muse-wonder-1.0" else "medium"},
        }
        if prev_id:
            kw["previous_response_id"] = prev_id
        response = client.responses.create(**kw)
        usage = getattr(response, "usage", None)
        if usage:
            totals["input_tokens"] += int(getattr(usage, "input_tokens", 0) or 0)
            totals["output_tokens"] += int(getattr(usage, "output_tokens", 0) or 0)
        prev_id = getattr(response, "id", None)
        toolcalls = [item for item in getattr(response, "output", []) if getattr(item, "type", None) == "function_call"]
        if toolcalls:
            if call_count + len(toolcalls) > MAX_TOOL_CALLS:
                raise ValueError("Model exceeded the tool-call budget")
            call_count += len(toolcalls)
            outputs = []
            for item in toolcalls:
                name = getattr(item, "name", "")
                args_text = getattr(item, "arguments", "")
                try:
                    args = json.loads(args_text)
                    value = tools.call(name, args)
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    value = {"error": f"Read-only tool rejected call: {type(exc).__name__}"}
                outputs.append({"type": "function_call_output", "call_id": item.call_id, "output": json.dumps(value)})
            payload = outputs
            continue
        text = getattr(response, "output_text", "")
        if not text:
            raise ValueError("Response contained no final JSON analysis")
        try:
            final = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("Response contained invalid JSON") from exc
        validate_report(final, tools.evidence_ids)
        break

    if final is None:
        raise ValueError("Model did not finish within the tool-round budget")
    # Scoring is NOT sent to the API. It exists only in this evaluation harness.
    return {
        "case": case.id, "model": model,
        "source": "live-meta-response", "expected": case.expected,
        "predicted": final["action"],
        "correct_action": final["action"] == case.expected,
        "inspection_count": call_count,
        "adequate_probing": call_count >= (0 if case.expected == "none" and case.id == "healthy" else 2),
        "grounded_evidence": True,
        "evidence_ids": final["evidence_ids"],
        "explanation": final["explanation"],
        "root_cause": final["root_cause"],
        "confidence": final["confidence"],
        "rounds": rounds,
        **totals,
        "estimated_usd_uncached": estimate_cost(model, totals["input_tokens"], totals["output_tokens"]),
        "elapsed_seconds": round(time.monotonic() - created, 2),
    }


def build_report(results: list[dict[str, Any]], model_names: list[str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "LIVE_META_API" if results else "DRY_RUN_NO_CALLS",
        "lab": "READ_ONLY_SYNTHETIC — no Docker, no real infrastructure, no repairs",
        "models": model_names,
        "case_count": len(CASES),
        "results": results,
        "overall": {
            "completed": sum("correct_action" in r for r in results),
            "correct": sum(r.get("correct_action") is True for r in results),
            "errors": sum("error" in r for r in results),
            "estimated_total_usd_uncached": round(sum(r.get("estimated_usd_uncached", 0) for r in results), 6),
        },
        "limitations": [
            "This evaluates proposed actions on six tiny synthetic incidents, not production reliability.",
            "The grade labels are withheld from the model; tool observations are synthetic.",
            "Correct answer does not mean safe repair; no repairs or live network probes occur.",
            "Latency and token cost depend on API access and run time; failures are included in the denominator.",
            "Reported model capability is not established until a real --live run succeeds.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark Meta's agentic fit for ProofOps (offline by default)")
    parser.add_argument("--live", action="store_true", help="Explicitly authorize real, billed Meta inference")
    parser.add_argument("--check", action="store_true", help="Run only a minimal Meta Responses API connectivity check")
    parser.add_argument("--models", default=DEFAULT_MODEL, help="Comma-separated models (Spark 1.3, Wonder 1.0)")
    parser.add_argument("--cases", default="all", help="Comma-separated case IDs or 'all'")
    parser.add_argument("--output", help="Optional sanitized JSON results filename")
    args = parser.parse_args(argv)
    models = [name.strip() for name in args.models.split(",")]
    if not models or any(name not in SUPPORTED_MODELS for name in models) or len(models) != len(set(models)):
        parser.error("--models must list unique supported model IDs")
    selected = list(CASES)
    if args.cases != "all":
        names = set(args.cases.split(","))
        selected = [case for case in CASES if case.id in names]
        if not selected or names != {case.id for case in selected}:
            parser.error("--cases contains an unknown case ID")

    print("ProofOps capability laboratory: read-only synthetic tasks; no repair execution")
    print("Models:", ", ".join(models), "| Cases:", ", ".join(c.id for c in selected))
    if not args.live:
        print("DRY RUN: no network calls and no charges. Run --live --check first to test API access.")
        print("Passing --live with --check performs one small real request per model.")
        print("Passing --live without --check runs the selected model×case trials and may be billed.")
        return 0
    key = os.environ.get("MODEL_API_KEY")
    if not key:
        print("ERROR: MODEL_API_KEY is not set; do not paste keys into chat or commands.", file=sys.stderr)
        return 2
    client = make_client(key)
    if args.check:
        failed = False
        for model in models:
            try:
                status = check_api(client, model)
                print(f"{model}: Responses API request accepted, text_returned={status['received_text']}")
                failed |= not (status["reachable"] and status["received_text"])
            except Exception as exc:
                print(f"{model}: FAILED ({short_error(exc)})")
                failed = True
        return 1 if failed else 0

    results = []
    for model in models:
        for case in selected:
            print(f"{model} / {case.id} ...", flush=True)
            try:
                row = investigate_case(client, model, case)
                print(f"   proposed={row['predicted']}, expected={row['expected']}, correct={row['correct_action']}, tools={row['inspection_count']}")
            except Exception as exc:
                row = {"case": case.id, "model": model, "expected": case.expected,
                       "error": short_error(exc), "source": "live-meta-response-or-client-error"}
                print(f"   FAILED: {row['error']}")
            results.append(row)
    report = build_report(results, models)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("Saved sanitized report:", path)
    print("Summary:", json.dumps(report["overall"], sort_keys=True))
    return 0 if all(r.get("correct_action") is True and r.get("adequate_probing") is True for r in results) else 1

if __name__ == "__main__":
    raise SystemExit(main())
