"""Domain-neutral, fail-closed verification of claimed repairs.

This verifier evaluates supplied *independent* observations and invariants. It
does not run code, contact external systems, or accept an AI's verdict as proof.
A caller must independently establish that observations are genuine.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence
import math


class Verdict(str, Enum):
    VERIFIED = "VERIFIED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class Invariant:
    key: str
    op: str
    expected: Any
    evidence_id: str

    def __post_init__(self) -> None:
        if not self.key or not self.evidence_id:
            raise ValueError("Invariant requires a key and independent evidence_id")
        if self.op not in {"eq", "ne", "gte", "lte"}:
            raise ValueError("Unsupported invariant operator")


@dataclass(frozen=True)
class Observation:
    evidence_id: str
    key: str
    value: Any
    source: str
    environment_fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.evidence_id, self.key, self.source, self.environment_fingerprint)):
            raise ValueError("Observation provenance is mandatory")


@dataclass(frozen=True)
class Check:
    key: str
    status: str
    evidence_id: str
    reason: str


@dataclass(frozen=True)
class Verification:
    verdict: Verdict
    checks: tuple[Check, ...]


def _holds(actual: Any, expected: Any, op: str) -> bool | None:
    if op in {"eq", "ne"}:
        # Strict value AND type equality: True must not count as 1.
        match = type(actual) is type(expected) and actual == expected
        return match if op == "eq" else not match
    if (
        isinstance(actual, bool) or isinstance(expected, bool)
        or not isinstance(actual, (int, float))
        or not isinstance(expected, (int, float))
    ):
        return None
    if not (math.isfinite(actual) and math.isfinite(expected)):
        return None
    return actual >= expected if op == "gte" else actual <= expected


def verify_repair(
    invariants: Sequence[Invariant],
    observations: Sequence[Observation],
    *,
    expected_environment: str,
    trusted_sources: frozenset[str],
) -> Verification:
    """A repair verifies only when every independent invariant holds.

    Duplicate IDs, conflicting observations, bad provenance, missing coverage,
    and non-comparable values fail closed. Contradictions outrank unknowns.
    """
    if not expected_environment or not trusted_sources or not invariants:
        return Verification(Verdict.INSUFFICIENT_EVIDENCE, ())
    # A single evidence ID must never satisfy multiple distinct requirements.
    # Otherwise a duplicated or contradictory rule can falsely imply coverage.
    rule_ids = [rule.evidence_id for rule in invariants]
    if len(rule_ids) != len(set(rule_ids)):
        return Verification(Verdict.INSUFFICIENT_EVIDENCE, ())
    lookup: dict[str, list[Observation]] = {}
    for obs in observations:
        lookup.setdefault(obs.evidence_id, []).append(obs)
    checks: list[Check] = []
    for rule in invariants:
        entries = lookup.get(rule.evidence_id, [])
        if len(entries) != 1:
            checks.append(Check(rule.key, "UNKNOWN", rule.evidence_id, "Missing or duplicate evidence"))
            continue
        obs = entries[0]
        if (
            obs.key != rule.key
            or obs.source not in trusted_sources
            or obs.environment_fingerprint != expected_environment
        ):
            checks.append(Check(rule.key, "UNKNOWN", rule.evidence_id, "Provenance or environment mismatch"))
            continue
        result = _holds(obs.value, rule.expected, rule.op)
        if result is None:
            checks.append(Check(rule.key, "UNKNOWN", rule.evidence_id, "Non-comparable observation"))
        elif result:
            checks.append(Check(rule.key, "PASS", rule.evidence_id, "Independent invariant satisfied"))
        else:
            checks.append(Check(rule.key, "FAIL", rule.evidence_id, "Independent invariant violated"))
    statuses = {item.status for item in checks}
    verdict = (
        Verdict.CONTRADICTED if "FAIL" in statuses
        else Verdict.INSUFFICIENT_EVIDENCE if "UNKNOWN" in statuses
        else Verdict.VERIFIED
    )
    return Verification(verdict, tuple(checks))
