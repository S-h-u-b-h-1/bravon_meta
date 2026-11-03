"""Typed domain model: intentionally no shell execution and no host configuration changes."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class LabConfig:
    """A deterministic *simulated* service graph, not a real DNS or Nginx configuration."""
    dns_record: str = "edge-proxy"
    proxy_upstream: str = "backend-a"
    backend_a_running: bool = True
    backend_b_running: bool = True

    def clone(self) -> "LabConfig":
        return LabConfig(**asdict(self))

    def payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Check:
    id: str
    name: str
    passed: bool
    observed: str
    expected: str
    detail: str

    def payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Diagnosis:
    summary: str
    root_cause: str
    action: str
    reasoning: str
    evidence_ids: list[str]
    source: str = "evidence-engine"
    confidence: float = 1.0
    model_note: str = ""

    def payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Verification:
    action: str
    before: list[Check]
    after: list[Check]
    tests_passed: int
    tests_total: int
    success: bool
    verified_revision: int
    state_fingerprint: str
    proof_digest: str
    verified_at: str = field(default_factory=utcnow)

    def payload(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "before": [c.payload() for c in self.before],
            "after": [c.payload() for c in self.after],
        }


@dataclass
class Incident:
    scenario: str
    label: str
    before_config: LabConfig
    detected_checks: list[Check]
    revision: int
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    opened_at: str = field(default_factory=utcnow)
    status: str = "open"
    diagnosis: Diagnosis | None = None
    verification: Verification | None = None
    executed_at: str | None = None
    recovery_proof: dict[str, Any] | None = None
    events: list[dict[str, str]] = field(default_factory=list)

    def event(self, title: str, description: str) -> None:
        self.events.append({"at": utcnow(), "title": title, "description": description})

    def payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scenario": self.scenario,
            "label": self.label,
            "revision": self.revision,
            "opened_at": self.opened_at,
            "status": self.status,
            "detected_checks": [c.payload() for c in self.detected_checks],
            "diagnosis": self.diagnosis.payload() if self.diagnosis else None,
            "verification": self.verification.payload() if self.verification else None,
            "executed_at": self.executed_at,
            "recovery_proof": self.recovery_proof,
            "events": list(self.events),
        }
