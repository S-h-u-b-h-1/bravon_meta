"""Incident state machine with independent sandbox verification and approval gates."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from hashlib import sha256
from threading import RLock
from typing import Any
import json

from .agent import MetaProvider, diagnose
from .domain import LabConfig, Incident, Verification, utcnow
from .probes import check_all, components, is_healthy
from .repairs import ACTIONS, safe_action


SCENARIOS: dict[str, dict[str, str]] = {
    "dns-drift": {
        "label": "DNS record drift",
        "description": "The app's DNS record unexpectedly resolves to an unknown target.",
        "impact": "Requests fail before reaching the gateway",
        "severity": "SEV-1",
    },
    "proxy-misroute": {
        "label": "Gateway misroute",
        "description": "The proxy is configured to send requests to a nonexistent upstream.",
        "impact": "Gateway receives traffic but cannot route it",
        "severity": "SEV-1",
    },
    "backend-outage": {
        "label": "Primary backend crash",
        "description": "Backend A becomes unavailable while healthy Backend B remains on standby.",
        "impact": "Active upstream fails; failover can restore traffic",
        "severity": "SEV-2",
    },
}


class ConflictError(Exception):
    pass


class NotFoundError(Exception):
    pass


def fingerprint(config: LabConfig) -> str:
    return sha256(json.dumps(config.payload(), sort_keys=True).encode()).hexdigest()


def proof_digest(payload: dict) -> str:
    """Checksummed trace for reproducibility, NOT a signature or external attestation."""
    return sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class IncidentLab:
    def __init__(self, provider: MetaProvider | None = None) -> None:
        self.lock = RLock()
        self.config = LabConfig()
        self.revision = 1
        self.incidents: dict[str, Incident] = {}
        self.active_id: str | None = None
        self.provider = provider

    def get(self, incident_id: str) -> Incident:
        try:
            return self.incidents[incident_id]
        except KeyError as exc:
            raise NotFoundError("Incident not found") from exc

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            checks = check_all(self.config)
            active = self.incidents.get(self.active_id) if self.active_id else None
            all_incidents = sorted(self.incidents.values(), key=lambda x: x.opened_at, reverse=True)
            resolved = [i for i in all_incidents if i.status == "recovered"]
            source_counts = Counter(i.diagnosis.source for i in all_incidents if i.diagnosis)
            return {
                "revision": self.revision,
                "lab_type": "deterministic-simulation",
                "live_infrastructure": False,
                "service_status": "healthy" if is_healthy(checks) else "critical",
                "components": components(self.config),
                "checks": [c.payload() for c in checks],
                "config": self.config.payload(),
                "active_incident": active.payload() if active else None,
                "incidents": [i.payload() for i in all_incidents[:30]],
                "scenarios": [{"id": k, **v} for k, v in SCENARIOS.items()],
                "metrics": {
                    "incidents": len(all_incidents),
                    "recovered": len(resolved),
                    "verified": sum(bool(i.verification and i.verification.success) for i in all_incidents),
                    "ai_assessments": source_counts.get("meta-muse", 0),
                    "passing_checks": sum(c.passed for c in checks),
                    "total_checks": len(checks),
                },
            }

    def inject(self, scenario: str) -> Incident:
        with self.lock:
            if scenario not in SCENARIOS:
                raise NotFoundError("Unknown scenario")
            active = self.incidents.get(self.active_id) if self.active_id else None
            if active and active.status != "recovered":
                raise ConflictError("Resolve current incident or reset lab before injecting another")
            self.config = LabConfig()
            if scenario == "dns-drift":
                self.config.dns_record = "unknown-target"
            elif scenario == "proxy-misroute":
                self.config.proxy_upstream = "legacy-backend"
            elif scenario == "backend-outage":
                self.config.backend_a_running = False
            self.revision += 1
            incident = Incident(
                scenario=scenario,
                label=SCENARIOS[scenario]["label"],
                before_config=self.config.clone(),
                detected_checks=check_all(self.config),
                revision=self.revision,
            )
            incident.event("Failure injected", SCENARIOS[scenario]["description"])
            self.incidents[incident.id] = incident
            self.active_id = incident.id
            return incident

    def _current(self, incident_id: str) -> Incident:
        incident = self.get(incident_id)
        if self.active_id != incident_id:
            raise ConflictError("Incident is not active")
        if incident.status == "recovered":
            raise ConflictError("Incident already recovered")
        return incident

    def analyze(self, incident_id: str, use_meta: bool = False) -> Incident:
        with self.lock:
            incident = self._current(incident_id)
            incident.diagnosis = diagnose(self.config, check_all(self.config), use_meta, self.provider)
            incident.verification = None
            incident.status = "diagnosed"
            incident.event("Root cause identified", f"{incident.diagnosis.source}: {incident.diagnosis.root_cause}")
            return incident

    def verify(self, incident_id: str) -> Incident:
        with self.lock:
            incident = self._current(incident_id)
            if not incident.diagnosis:
                raise ConflictError("Diagnose first")
            if incident.revision != self.revision:
                raise ConflictError("Environment changed since incident was detected")
            before = check_all(self.config)
            after_config = safe_action(incident.diagnosis.action, self.config)
            after = check_all(after_config)
            success = is_healthy(after)
            trace = {
                "action": incident.diagnosis.action,
                "before": [asdict(c) for c in before],
                "after": [asdict(c) for c in after],
                "before_fingerprint": fingerprint(self.config),
                "after_fingerprint": fingerprint(after_config),
                "revision": self.revision,
            }
            incident.verification = Verification(
                action=incident.diagnosis.action,
                before=before,
                after=after,
                tests_passed=sum(c.passed for c in after),
                tests_total=len(after),
                success=success,
                verified_revision=self.revision,
                state_fingerprint=fingerprint(self.config),
                proof_digest=proof_digest(trace),
            )
            incident.status = "verified" if success else "verification-failed"
            incident.event(
                "Sandbox verification " + ("passed" if success else "failed"),
                f"{incident.verification.tests_passed}/{incident.verification.tests_total} invariant checks passed on a cloned state.",
            )
            return incident

    def execute(self, incident_id: str, approved: bool, expected_revision: int) -> Incident:
        with self.lock:
            incident = self._current(incident_id)
            if not approved:
                raise ConflictError("Explicit operator approval is required")
            verification = incident.verification
            if not verification or not verification.success or incident.status != "verified":
                raise ConflictError("A successful sandbox verification is required")
            if (expected_revision != self.revision
                    or verification.verified_revision != self.revision
                    or verification.state_fingerprint != fingerprint(self.config)):
                raise ConflictError("Verification stale: re-run checks before applying")
            original = self.config.clone()
            try:
                candidate = safe_action(verification.action, self.config)
                final_checks = check_all(candidate)
                if not is_healthy(final_checks):
                    raise RuntimeError("Post-change regression checks failed")
                # Replace state atomically only after independent successful health probes.
                self.config = candidate
                self.revision += 1
                incident.status = "recovered"
                incident.executed_at = utcnow()
                incident.recovery_proof = {
                    "before_fingerprint": fingerprint(original),
                    "after_fingerprint": fingerprint(candidate),
                    "verification_digest": verification.proof_digest,
                    "post_change_checks": [c.payload() for c in final_checks],
                    "result": "recovered-in-simulated-lab",
                    "revision": self.revision,
                }
                incident.event("Repair applied", ACTIONS[verification.action].label)
                incident.event("Recovery confirmed", "All post-change simulated probes passed.")
            except Exception:
                self.config = original
                incident.event("Repair aborted", "Configuration rolled back after failed health verification.")
                raise
            return incident

    def reset(self) -> dict[str, Any]:
        with self.lock:
            active = self.incidents.get(self.active_id) if self.active_id else None
            if active and active.status != "recovered":
                active.status = "abandoned"
                active.event("Lab reset", "Operator reset synthetic topology.")
            self.active_id = None
            self.config = LabConfig()
            self.revision += 1
            return self.snapshot()
