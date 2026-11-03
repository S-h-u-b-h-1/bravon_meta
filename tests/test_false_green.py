"""Regression tests for the first Bravon false-green repair challenge."""
from bravon_verification import Invariant, Observation, Verdict, verify_repair


def evaluate(values, *, fingerprint="fixture-v1", source="independent-oracle"):
    rules = [
        Invariant("original_test_passes", "eq", True, "e1"),
        Invariant("negative_quantity_rejected", "eq", True, "e2"),
        Invariant("refund_total", "eq", 100, "e3"),
    ]
    obs = [
        Observation(f"e{i}", key, value, source, fingerprint)
        for i, (key, value) in enumerate(zip(
            ["original_test_passes", "negative_quantity_rejected", "refund_total"],
            values
        ), 1)
    ]
    return verify_repair(
        rules, obs, expected_environment="fixture-v1",
        trusted_sources=frozenset({"independent-oracle"}),
    )


def test_narrow_tests_green_but_hidden_invariant_fails():
    result = evaluate([True, False, 100])
    assert result.verdict == Verdict.CONTRADICTED
    assert [c.status for c in result.checks] == ["PASS", "FAIL", "PASS"]


def test_all_independent_invariants_pass():
    assert evaluate([True, True, 100]).verdict == Verdict.VERIFIED


def test_wrong_environment_cannot_verify():
    assert evaluate([True, True, 100], fingerprint="stale-fixture").verdict == Verdict.INSUFFICIENT_EVIDENCE


def test_untrusted_source_cannot_verify():
    assert evaluate([True, True, 100], source="candidate-ai").verdict == Verdict.INSUFFICIENT_EVIDENCE


def test_missing_or_duplicate_evidence_fails_closed():
    rules = [Invariant("x", "eq", True, "e1")]
    def obs():
        return Observation("e1", "x", True, "oracle", "v1")
    kwargs = dict(expected_environment="v1", trusted_sources=frozenset({"oracle"}))
    assert verify_repair(rules, [], **kwargs).verdict == Verdict.INSUFFICIENT_EVIDENCE
    assert verify_repair(rules, [obs(), obs()], **kwargs).verdict == Verdict.INSUFFICIENT_EVIDENCE


def test_boolean_does_not_pass_numeric_equality():
    r = [Invariant("count", "eq", 1, "e")]
    o = [Observation("e", "count", True, "oracle", "v1")]
    assert verify_repair(r, o, expected_environment="v1", trusted_sources=frozenset({"oracle"})).verdict == Verdict.CONTRADICTED


def test_empty_coverage_cannot_verify():
    assert verify_repair([], [], expected_environment="v1", trusted_sources=frozenset({"oracle"})).verdict == Verdict.INSUFFICIENT_EVIDENCE


def test_reused_evidence_id_cannot_prove_two_invariants():
    rules = [Invariant("check_a", "eq", True, "same"), Invariant("check_b", "eq", True, "same")]
    obs = [Observation("same", "check_a", True, "oracle", "v1")]
    outcome = verify_repair(rules, obs, expected_environment="v1", trusted_sources=frozenset({"oracle"}))
    assert outcome.verdict == Verdict.INSUFFICIENT_EVIDENCE
