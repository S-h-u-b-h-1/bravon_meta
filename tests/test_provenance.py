"""Integrity, scope and replay checks for the Bravon evidence envelope."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import time

import pytest

from bravon_provenance import (
    MemoryReplayStore, SQLiteReplayStore, authenticate_evidence, sign_evidence,
    verify_signed_repair,
)
from bravon_verification import Invariant, Observation, Verdict

KEY = b"a" * 32
KEY_ID = "key-2026-10"
NOW = int(time.time())
OBS = (Observation("e1", "tests_green", True, "runner-1", "env-v1"),)


def signed():
    return sign_evidence(runner_id="runner-1", key_id=KEY_ID, case_id="case-1",
                         nonce="n1", issued_at=NOW, observations=OBS, secret=KEY)


def verify(envelope, store=None, case_id="case-1", now=NOW):
    return authenticate_evidence(envelope, case_id=case_id,
        runner_keys={("runner-1", KEY_ID): KEY},
        replay_store=store or MemoryReplayStore(), now=now)


def test_valid_signature_authenticates():
    assert verify(signed()) == OBS


def test_observation_tampering_fails():
    changed = (replace(OBS[0], value=False),)
    assert verify(replace(signed(), observations=changed)) is None


def test_case_binding_fails_closed():
    assert verify(signed(), case_id="case-2") is None


def test_unknown_runner_fails():
    assert verify(replace(signed(), runner_id="unknown")) is None


def test_invalid_signature_fails():
    assert verify(replace(signed(), signature="0" * 64)) is None


def test_nonce_replay_fails():
    store = MemoryReplayStore()
    assert verify(signed(), store) == OBS
    assert verify(signed(), store) is None


def test_invalid_proof_does_not_consume_nonce():
    store = MemoryReplayStore()
    assert verify(replace(signed(), signature="0" * 64), store) is None
    assert verify(signed(), store) == OBS


def test_short_secret_refused():
    with pytest.raises(ValueError):
        sign_evidence(runner_id="runner-1", case_id="case-1",
                      key_id=KEY_ID, nonce="n1", observations=OBS, secret=b"short")


def test_stale_or_future_evidence_fails_closed():
    assert verify(signed(), now=NOW + 301) is None
    assert verify(signed(), now=NOW - 31) is None


def test_key_identity_is_authenticated():
    assert verify(replace(signed(), key_id="retired-key")) is None


def test_sqlite_replay_is_durable_across_store_instances(tmp_path):
    path = tmp_path / "replay.sqlite3"
    assert verify(signed(), SQLiteReplayStore(path)) == OBS
    assert verify(signed(), SQLiteReplayStore(path)) is None


def test_sqlite_replay_claim_is_atomic_across_threads(tmp_path):
    store = SQLiteReplayStore(tmp_path / "replay.sqlite3")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: verify(signed(), store), range(8)))
    assert results.count(OBS) == 1
    assert results.count(None) == 7


def test_replay_store_failure_fails_closed():
    class BrokenStore:
        def consume(self, replay_id):
            raise OSError("storage unavailable")

    assert verify(signed(), BrokenStore()) is None


def test_authenticated_evidence_can_verify_independent_check():
    signed_proof = signed()
    result = verify_signed_repair(
        signed_proof, case_id="case-1",
        invariants=(Invariant("tests_green", "eq", True, "e1"),),
        expected_environment="env-v1",
        runner_keys={("runner-1", KEY_ID): KEY},
        replay_store=MemoryReplayStore(),
    )
    assert result.verdict == Verdict.VERIFIED


def test_signed_observation_cannot_impersonate_other_source():
    forged = (replace(OBS[0], source="independent-oracle"),)
    proof = sign_evidence(runner_id="runner-1", key_id=KEY_ID, case_id="case-1",
                          nonce="n-source", issued_at=NOW, observations=forged, secret=KEY)
    result = verify_signed_repair(
        proof, case_id="case-1",
        invariants=(Invariant("tests_green", "eq", True, "e1"),),
        expected_environment="env-v1",
        runner_keys={("runner-1", KEY_ID): KEY},
        replay_store=MemoryReplayStore(),
    )
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE


def test_valid_signature_but_wrong_environment_is_not_verified():
    result = verify_signed_repair(
        signed(), case_id="case-1",
        invariants=(Invariant("tests_green", "eq", True, "e1"),),
        expected_environment="env-changed",
        runner_keys={("runner-1", KEY_ID): KEY},
        replay_store=MemoryReplayStore(),
    )
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE


def test_signed_proof_replay_cannot_verify_twice():
    consumed = MemoryReplayStore()
    params = dict(case_id="case-1",
        invariants=(Invariant("tests_green", "eq", True, "e1"),),
        expected_environment="env-v1", runner_keys={("runner-1", KEY_ID): KEY},
        replay_store=consumed)
    assert verify_signed_repair(signed(), **params).verdict == Verdict.VERIFIED
    assert verify_signed_repair(signed(), **params).verdict == Verdict.INSUFFICIENT_EVIDENCE
