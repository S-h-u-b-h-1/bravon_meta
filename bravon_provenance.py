"""HMAC integrity envelopes for trusted-runner observations.

This is a transport-integrity boundary, not proof that a runner was independent
or that its measurements are truthful. The verifier must keep runner keys private
and maintain durable nonce replay state in production.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
from pathlib import Path
import re
import sqlite3
import threading
import time
from typing import Any, Mapping, Protocol

from bravon_verification import Observation


@dataclass(frozen=True)
class SignedEvidence:
    runner_id: str
    key_id: str
    case_id: str
    nonce: str
    issued_at: int
    observations: tuple[Observation, ...]
    signature: str


ReplayId = tuple[str, str, str]
_HEX_SIGNATURE = re.compile(r"^[0-9a-f]{64}$")
_MAX_ID_LENGTH = 256
_MAX_OBSERVATIONS = 100


class ReplayStore(Protocol):
    def consume(self, replay_id: ReplayId) -> bool: ...


class MemoryReplayStore:
    """Atomic process-local replay store for tests and single-process tools."""

    def __init__(self) -> None:
        self._used: set[ReplayId] = set()
        self._lock = threading.Lock()

    def consume(self, replay_id: ReplayId) -> bool:
        with self._lock:
            if replay_id in self._used:
                return False
            self._used.add(replay_id)
            return True


class SQLiteReplayStore:
    """Durable replay store using an atomic SQLite uniqueness constraint."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path == ":memory:":
            raise ValueError("Use MemoryReplayStore for in-memory replay state")
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS evidence_nonces (
                       runner_id TEXT NOT NULL,
                       case_id TEXT NOT NULL,
                       nonce TEXT NOT NULL,
                       consumed_at INTEGER NOT NULL,
                       PRIMARY KEY (runner_id, case_id, nonce)
                   ) WITHOUT ROWID"""
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def consume(self, replay_id: ReplayId) -> bool:
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "INSERT OR IGNORE INTO evidence_nonces VALUES (?, ?, ?, ?)",
                    (*replay_id, int(time.time())),
                )
                return cursor.rowcount == 1
        except sqlite3.Error:
            return False


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and 0 < len(value) <= _MAX_ID_LENGTH


def _payload(runner_id: str, key_id: str, case_id: str, nonce: str, issued_at: int,
             observations: tuple[Observation, ...]) -> bytes:
    data = {
        "schema": "bravon.evidence-envelope.v2",
        "runner_id": runner_id,
        "key_id": key_id,
        "case_id": case_id,
        "nonce": nonce,
        "issued_at": issued_at,
        "observations": [
            {
                "evidence_id": o.evidence_id,
                "key": o.key,
                "value": o.value,
                "source": o.source,
                "environment_fingerprint": o.environment_fingerprint,
            }
            for o in observations
        ],
    }
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sign_evidence(*, runner_id: str, key_id: str, case_id: str, nonce: str,
                  observations: tuple[Observation, ...], secret: bytes,
                  issued_at: int | None = None) -> SignedEvidence:
    issued_at = int(time.time()) if issued_at is None else issued_at
    ids = (runner_id, key_id, case_id, nonce)
    if (not all(_valid_id(value) for value in ids)
            or type(issued_at) is not int or issued_at <= 0
            or not isinstance(secret, bytes) or len(secret) < 32
            or not isinstance(observations, tuple)
            or not 0 < len(observations) <= _MAX_OBSERVATIONS):
        raise ValueError("Bounded runner, key, case, nonce, timestamp, observations and >=32-byte secret are required")
    signature = hmac.new(
        secret, _payload(runner_id, key_id, case_id, nonce, issued_at, observations), sha256,
    ).hexdigest()
    return SignedEvidence(runner_id, key_id, case_id, nonce, issued_at, observations, signature)


def authenticate_evidence(
    envelope: SignedEvidence, *, case_id: str,
    runner_keys: Mapping[tuple[str, str], bytes], replay_store: ReplayStore,
    now: int | None = None, max_age_seconds: int = 300,
    max_future_skew_seconds: int = 30,
) -> tuple[Observation, ...] | None:
    """Authenticate first, then atomically consume the durable replay ID."""
    now = int(time.time()) if now is None else now
    ids = (envelope.runner_id, envelope.key_id, envelope.case_id, envelope.nonce)
    if (not all(_valid_id(value) for value in ids)
            or not _valid_id(case_id) or envelope.case_id != case_id
            or type(envelope.issued_at) is not int or type(now) is not int
            or type(max_age_seconds) is not int or max_age_seconds <= 0
            or type(max_future_skew_seconds) is not int or max_future_skew_seconds < 0
            or now - envelope.issued_at > max_age_seconds
            or envelope.issued_at - now > max_future_skew_seconds
            or not isinstance(envelope.observations, tuple)
            or not 0 < len(envelope.observations) <= _MAX_OBSERVATIONS
            or not isinstance(envelope.signature, str)
            or not _HEX_SIGNATURE.fullmatch(envelope.signature)):
        return None
    key = runner_keys.get((envelope.runner_id, envelope.key_id))
    if not isinstance(key, bytes) or len(key) < 32:
        return None
    replay_id = (envelope.runner_id, envelope.case_id, envelope.nonce)
    try:
        computed = hmac.new(
            key,
            _payload(envelope.runner_id, envelope.key_id, envelope.case_id,
                     envelope.nonce, envelope.issued_at, envelope.observations),
            sha256,
        ).hexdigest()
    except (TypeError, ValueError, OverflowError):
        return None
    if not hmac.compare_digest(computed, envelope.signature):
        return None
    try:
        return envelope.observations if replay_store.consume(replay_id) else None
    except Exception:
        return None

def verify_signed_repair(
    envelope: SignedEvidence,
    *,
    case_id: str,
    invariants: tuple["Invariant", ...],
    expected_environment: str,
    runner_keys: Mapping[tuple[str, str], bytes],
    replay_store: ReplayStore,
) -> "Verification":
    """Qualify only authenticated observations sourced from their signing runner.

    A signed result does not establish that a runner or its tests are honest.
    """
    from bravon_verification import Invariant, Verification, Verdict, verify_repair

    observations = authenticate_evidence(
        envelope, case_id=case_id, runner_keys=runner_keys, replay_store=replay_store,
    )
    if observations is None:
        return Verification(Verdict.INSUFFICIENT_EVIDENCE, ())
    if any(o.source != envelope.runner_id for o in observations):
        return Verification(Verdict.INSUFFICIENT_EVIDENCE, ())
    if any(o.environment_fingerprint != expected_environment for o in observations):
        return Verification(Verdict.INSUFFICIENT_EVIDENCE, ())
    return verify_repair(
        invariants, observations,
        expected_environment=expected_environment,
        trusted_sources=frozenset({envelope.runner_id}),
    )
