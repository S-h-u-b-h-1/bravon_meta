"""Strict import of independently executed before/after regression evidence.

Only validates a report supplied by an external trusted runner. It never clones,
installs dependencies, or executes repository code. Untrusted fields cannot
turn error/skip/timeout into proof of a repaired regression.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class DifferentialRecord:
    repository: str
    before_commit: str
    after_commit: str
    test_id: str
    before: str
    after: str
    execution_id: str


@dataclass(frozen=True)
class DifferentialDecision:
    status: str
    explanation: str


_ALLOWED = frozenset({"PASS", "ASSERT_FAIL", "ERROR", "SKIP", "TIMEOUT", "UNKNOWN"})


def assess_differential(record: DifferentialRecord) -> DifferentialDecision:
    """Recognize actual assertion-failure to pass transitions, not general correctness."""
    fields = (record.repository, record.before_commit, record.after_commit,
              record.test_id, record.execution_id)
    if any(not isinstance(value, str) or not value.strip() for value in fields):
        return DifferentialDecision("INCONCLUSIVE", "Required identity or execution evidence missing")
    if (record.before_commit == record.after_commit or
            not isinstance(record.before, str) or not isinstance(record.after, str) or
            record.before not in _ALLOWED or record.after not in _ALLOWED):
        return DifferentialDecision("INCONCLUSIVE", "Revision distinction or test outcome invalid")
    if record.before == "ASSERT_FAIL" and record.after == "PASS":
        return DifferentialDecision("REGRESSION_OBSERVED",
                                    "An assertion failure before the fix passed afterward; scope limited to this test")
    if record.before in {"ERROR", "SKIP", "TIMEOUT", "UNKNOWN"} or record.after in {
        "ERROR", "SKIP", "TIMEOUT", "UNKNOWN"
    }:
        return DifferentialDecision("INCONCLUSIVE", "Test execution did not provide comparable outcomes")
    if record.after == "ASSERT_FAIL":
        return DifferentialDecision("FIX_FAILS", "Selected regression assertion still fails after patch")
    return DifferentialDecision("NOT_DEMONSTRATED", "No assertion-failure to pass transition demonstrated")
