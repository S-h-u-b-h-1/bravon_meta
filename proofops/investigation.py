"""Read-only, provider-neutral investigation of the disposable ProofOps Docker network.

The reference investigator is explicitly deterministic; it is NOT an AI model.
It exercises the exact tool/evidence boundary a later model may use. Neither
untrusted text nor a model gets Docker shell access. Decisions are proposals;
verification and repair remain wholly inside DockerLab's existing gates.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Protocol

from .real_lab import APP_HOST, ACTIONS, ComposeStack, LabConflict

MAX_CALLS = 8
MAX_RESPONSE_CHARS = 2400
TOOL_NAMES = frozenset({"topology", "customer_path", "lookup_dns", "inspect_gateway", "probe_backend"})


@dataclass(frozen=True)
class ToolStep:
    name: str
    arguments: dict[str, str]


@dataclass(frozen=True)
class FinalStep:
    action: str
    root_cause: str
    explanation: str
    evidence_ids: tuple[str, ...]
    confidence: float


class InvestigatorAgent(Protocol):
    """May choose a tool or return a final proposal; never executes a repair."""
    def next_step(self, observations: tuple[dict[str, Any], ...]) -> ToolStep | FinalStep: ...


class RealReadOnlyTools:
    """Five fixed, bounded Docker read-only probes. No arbitrary Docker CLI parameters."""

    def __init__(self, stack: ComposeStack):
        self._stack = stack
        self._seen: list[dict[str, Any]] = []

    @property
    def observations(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._seen)

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in TOOL_NAMES:
            raise ValueError("Read-only tool is not allowlisted")
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object")
        if name != "probe_backend" and arguments:
            raise ValueError("Unexpected arguments for read-only probe")
        if name == "probe_backend" and (
            set(arguments) != {"backend"} or arguments["backend"] not in ("backend-a", "backend-b")
        ):
            raise ValueError("Only backend-a and backend-b may be probed")
        if len(self._seen) >= MAX_CALLS:
            raise LabConflict("Read-only investigation exhausted its tool-call budget")

        stack = self._stack
        if name == "topology":
            result = {
                "evidence_id": "topology", "host": APP_HOST, "expected_resolver_ip": stack.dns_ip,
                "expected_gateway_ip": stack.edge_ip,
                "declared_backends": {"backend-a": stack.backend_a_ip, "backend-b": stack.backend_b_ip},
            }
        elif name == "lookup_dns":
            query = stack.run("exec", "-T", "probe", "nslookup", APP_HOST, stack.dns_ip,
                              strict=False, timeout=10)
            addresses = re.findall(r"Address(?:\s+\d+)?:\s*(\d{1,3}(?:\.\d{1,3}){3})", query.stdout)
            ip = next((addr for addr in reversed(addresses) if addr != stack.dns_ip), "unresolved")
            result = {"evidence_id": "dns", "resolved_ip": ip, "expected_ip": stack.edge_ip,
                      "matches_expected": query.code == 0 and ip == stack.edge_ip}
        elif name == "inspect_gateway":
            query = stack.run("exec", "-T", "edge", "nginx", "-T", strict=False, timeout=12)
            matches = re.findall(r"\bproxy_pass\s+http://(\d{1,3}(?:\.\d{1,3}){3}):8080\s*;",
                                 query.stdout + "\n" + query.stderr)
            ip = matches[-1] if matches else "unresolved"
            result = {"evidence_id": "gateway", "upstream_ip": ip,
                      "declared_ips": [stack.backend_a_ip, stack.backend_b_ip],
                      "allowed": query.code == 0 and ip in {stack.backend_a_ip, stack.backend_b_ip}}
        elif name == "probe_backend":
            backend = arguments["backend"]
            ip = stack.backend_a_ip if backend == "backend-a" else stack.backend_b_ip
            body = stack._http(f"http://{ip}:8080/health")
            result = {"evidence_id": backend, "backend": backend,
                      "healthy": bool(body and body.get("backend") == backend and body.get("status") == "ok")}
        else:
            body = stack._http(f"http://{APP_HOST}:8080/health")
            result = {"evidence_id": "customer-path", "healthy": bool(
                body and body.get("status") == "ok" and body.get("backend") in {"backend-a", "backend-b"}),
                "serving_backend": body.get("backend") if isinstance(body, dict) else None}
        if len(json.dumps(result)) > MAX_RESPONSE_CHARS:
            raise LabConflict("Probe output unexpectedly exceeded bounded evidence size")
        self._seen.append(result)
        return result


class ReferenceInvestigator:
    """Offline evidence-driven *rule baseline*, not independent AI reasoning.

    Reads every crucial signal to avoid single-fault bias, including compounds
    and unavailable standby. Intended to benchmark later model-selected probes.
    """
    PLAN = (
        ToolStep("topology", {}),
        ToolStep("customer_path", {}),
        ToolStep("lookup_dns", {}),
        ToolStep("inspect_gateway", {}),
        ToolStep("probe_backend", {"backend": "backend-a"}),
        ToolStep("probe_backend", {"backend": "backend-b"}),
    )

    def next_step(self, observations: tuple[dict[str, Any], ...]) -> ToolStep | FinalStep:
        if len(observations) < len(self.PLAN):
            return self.PLAN[len(observations)]
        lookup = {o["evidence_id"]: o for o in observations}
        top = lookup["topology"]
        customer = lookup["customer-path"]
        dns = lookup["dns"]
        gateway = lookup["gateway"]
        a = lookup["backend-a"]
        b = lookup["backend-b"]
        failures = []
        if not dns["matches_expected"]:
            failures.append("DNS answer does not match the declared gateway")
        upstream = gateway["upstream_ip"]
        if not gateway["allowed"]:
            failures.append("Nginx upstream is outside the declared backends")
        elif upstream == top["declared_backends"]["backend-a"] and not a["healthy"]:
            failures.append("Selected primary backend did not respond")
        elif upstream == top["declared_backends"]["backend-b"] and not b["healthy"]:
            failures.append("Selected standby backend did not respond")
        action = "none"
        if customer["healthy"]:
            cause = "No customer-facing outage was observed"
            explanation = "No repair proposed for a healthy customer path."
        elif len(failures) > 1:
            cause = "; ".join(failures)
            explanation = "Multiple faults require more than one safe repair; abstaining."
        elif len(failures) == 0:
            cause = "Customer path failed without a supported single-fault explanation"
            explanation = "Insufficient evidence for an allowlisted repair."
        elif not dns["matches_expected"] and gateway["allowed"] and (
            (upstream == top["declared_backends"]["backend-a"] and a["healthy"]) or
            (upstream == top["declared_backends"]["backend-b"] and b["healthy"])
        ):
            action = "restore_dns"
            cause = failures[0]
            explanation = "DNS differs from the expected gateway; selected upstream is ready."
        elif not gateway["allowed"] and dns["matches_expected"] and a["healthy"]:
            action = "restore_proxy"
            cause = failures[0]
            explanation = "Nginx targets an invalid backend; healthy primary can be restored."
        elif gateway["allowed"] and upstream == top["declared_backends"]["backend-a"] and (
            not a["healthy"] and b["healthy"] and dns["matches_expected"]
        ):
            action = "failover"
            cause = failures[0]
            explanation = "Primary is down and independent standby passed its direct health probe."
        else:
            cause = failures[0]
            explanation = "Evidence does not establish a safe one-step repair; abstaining."
        return FinalStep(action=action, root_cause=cause, explanation=explanation,
                         evidence_ids=tuple(o["evidence_id"] for o in observations),
                         confidence=1.0 if action != "none" else 0.0)


def investigate_readonly(tools: RealReadOnlyTools, agent: InvestigatorAgent, *, label: str) -> dict[str, Any]:
    """Provider neutral tool loop, strict arguments, budgets, citations and abstention."""
    if not label or len(label) > 100:
        raise ValueError("Invalid provider label")
    transcript: list[dict[str, Any]] = []
    for step_index in range(MAX_CALLS + 1):
        step = agent.next_step(tools.observations)
        if isinstance(step, ToolStep):
            if step_index >= MAX_CALLS:
                raise LabConflict("No final proposal before read-only tool budget expired")
            response = tools.call(step.name, step.arguments)
            transcript.append({"kind": "tool", "name": step.name, "arguments": dict(step.arguments),
                               "evidence": response})
            continue
        if not isinstance(step, FinalStep):
            raise LabConflict("Investigator must return a fixed tool call or a structured proposal")
        if step.action != "none" and step.action not in ACTIONS:
            raise LabConflict("Proposed repair is not on the allowed repair list")
        if not isinstance(step.confidence, (int, float)) or isinstance(step.confidence, bool) or not 0 <= step.confidence <= 1:
            raise LabConflict("Confidence is outside 0..1")
        if not (step.root_cause.strip() and step.explanation.strip()) or len(step.root_cause) > 1000 or len(step.explanation) > 1000:
            raise LabConflict("Investigator explanation is missing or oversized")
        available = {o["evidence_id"] for o in tools.observations}
        citations = set(step.evidence_ids)
        if not citations.issubset(available) or (step.action != "none" and not citations):
            raise LabConflict("Proposed action cites unobserved or no evidence")
        proposal = {"action": step.action, "root_cause": step.root_cause,
                    "explanation": step.explanation, "evidence_ids": list(step.evidence_ids),
                    "confidence": step.confidence, "source": label}
        transcript.append({"kind": "proposal", **proposal})
        return {"proposal": proposal, "transcript": transcript,
                "tool_calls": len(transcript) - 1, "read_only": True, "executed_repair": False}
    raise LabConflict("Read-only investigation exceeded its budget")
