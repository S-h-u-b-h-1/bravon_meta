from dataclasses import replace

from bravon_execution_contract import ExecutionManifest
from bravon_signed_execution import assess_signed_execution, manifest_digest
from bravon_provenance import MemoryReplayStore, sign_evidence
from bravon_verification import Observation

KEY = b"x" * 32
KEY_ID = "key-1"
M = ExecutionManifest(
    repository="example/library", before_commit="a"*40, after_commit="b"*40,
    test_id="tests/test_regression.py::test_bug", execution_id="execution-1",
    runner_id="isolated-runner", image_digest="sha256:" + "c"*64,
    before_run_id="before-1", after_run_id="after-1",
    before_status="ASSERT_FAIL", after_status="PASS",
)


def envelope(manifest=M, *, claimed_runner=None):
    runner = claimed_runner or manifest.runner_id
    obs = (Observation("manifest-digest", "execution_manifest_sha256",
                       manifest_digest(manifest), runner, manifest.image_digest),)
    return sign_evidence(
        runner_id=runner, key_id=KEY_ID, case_id=manifest.execution_id,
        nonce="fresh-1", observations=obs, secret=KEY,
    )


def assess(manifest, proof, replay_store=None):
    return assess_signed_execution(
        manifest, proof, runner_keys={("isolated-runner", KEY_ID): KEY},
        replay_store=replay_store or MemoryReplayStore(),
    )


def test_correctly_signed_manifest_records_narrow_regression():
    assert assess(M, envelope()).status == "REGRESSION_OBSERVED"


def test_changed_outcome_invalidates_signed_manifest():
    assert assess(replace(M, after_status="ASSERT_FAIL"), envelope()).status == "INCONCLUSIVE"


def test_changed_repository_invalidates_signed_manifest():
    assert assess(replace(M, repository="another/repo"), envelope()).status == "INCONCLUSIVE"


def test_replay_refused():
    store = MemoryReplayStore()
    assert assess(M, envelope(), store).status == "REGRESSION_OBSERVED"
    assert assess(M, envelope(), store).status == "INCONCLUSIVE"


def test_signer_identity_must_match_manifest():
    assert assess(M, envelope(claimed_runner="impersonator")).status == "INCONCLUSIVE"


def test_tampered_signature_rejected():
    assert assess(M, replace(envelope(), signature="0"*64)).status == "INCONCLUSIVE"


def test_timeout_not_promoted_even_when_signed():
    bad = replace(M, before_status="TIMEOUT")
    assert assess(bad, envelope(bad)).status == "INCONCLUSIVE"
