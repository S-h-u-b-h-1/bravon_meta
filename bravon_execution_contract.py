"""Conservative contract for independent two-revision test execution.

This module validates recorded job identity and outcomes. It never executes a
repository, authenticates an external runner, or treats metadata as attestation.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

from bravon_differential import DifferentialRecord, DifferentialDecision, assess_differential

_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class ExecutionManifest:
    repository: str
    before_commit: str
    after_commit: str
    test_id: str
    execution_id: str
    runner_id: str
    image_digest: str
    before_run_id: str
    after_run_id: str
    before_status: str
    after_status: str


def assess_execution(manifest: ExecutionManifest) -> DifferentialDecision:
    values = (
        manifest.repository, manifest.test_id, manifest.execution_id,
        manifest.runner_id, manifest.before_run_id, manifest.after_run_id,
    )
    if any(not isinstance(v, str) or not v.strip() for v in values):
        return DifferentialDecision("INCONCLUSIVE", "Missing execution identity")
    if not _SHA.fullmatch(manifest.before_commit) or not _SHA.fullmatch(manifest.after_commit):
        return DifferentialDecision("INCONCLUSIVE", "Commit identifiers must be full lowercase SHA-1 IDs")
    if not _DIGEST.fullmatch(manifest.image_digest):
        return DifferentialDecision("INCONCLUSIVE", "An immutable execution-image digest is required")
    if manifest.before_run_id == manifest.after_run_id:
        return DifferentialDecision("INCONCLUSIVE", "Before and after must be distinct executions")
    record = DifferentialRecord(
        repository=manifest.repository,
        before_commit=manifest.before_commit,
        after_commit=manifest.after_commit,
        test_id=manifest.test_id,
        before=manifest.before_status,
        after=manifest.after_status,
        execution_id=manifest.execution_id,
    )
    return assess_differential(record)
