"""Bind a differential test manifest to authenticated runner observations.

A digest matching a signed envelope is integrity evidence, *not* attestation
that the isolated job actually ran. No untrusted programs are executed here.
"""
from __future__ import annotations
from dataclasses import asdict
from hashlib import sha256
import json
from typing import Mapping

from bravon_execution_contract import ExecutionManifest, assess_execution
from bravon_provenance import ReplayStore, SignedEvidence, authenticate_evidence
from bravon_differential import DifferentialDecision


def manifest_digest(manifest: ExecutionManifest) -> str:
    payload = json.dumps(
        {"schema": "bravon.execution-manifest.v1", "manifest": asdict(manifest)},
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + sha256(payload).hexdigest()


def assess_signed_execution(
    manifest: ExecutionManifest,
    envelope: SignedEvidence,
    *,
    runner_keys: Mapping[tuple[str, str], bytes],
    replay_store: ReplayStore,
) -> DifferentialDecision:
    if not manifest.execution_id or envelope.runner_id != manifest.runner_id:
        return DifferentialDecision("INCONCLUSIVE", "Runner identity mismatch")
    if envelope.case_id != manifest.execution_id:
        return DifferentialDecision("INCONCLUSIVE", "Execution identity mismatch")
    # Check the manifest before consuming a signed nonce.
    preliminary = assess_execution(manifest)
    if preliminary.status == "INCONCLUSIVE":
        return preliminary
    observations = authenticate_evidence(
        envelope, case_id=manifest.execution_id,
        runner_keys=runner_keys, replay_store=replay_store,
    )
    if observations is None or len(observations) != 1:
        return DifferentialDecision("INCONCLUSIVE", "Missing or invalid authenticated evidence")
    proof = observations[0]
    if (proof.evidence_id != "manifest-digest"
            or proof.key != "execution_manifest_sha256"
            or proof.source != manifest.runner_id
            or proof.environment_fingerprint != manifest.image_digest
            or type(proof.value) is not str
            or proof.value != manifest_digest(manifest)):
        return DifferentialDecision("INCONCLUSIVE", "Signed observation does not match execution manifest")
    return preliminary
