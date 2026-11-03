from bravon_differential import DifferentialRecord, assess_differential


def case(before="ASSERT_FAIL", after="PASS", **changes):
    data = dict(repository="example/project", before_commit="a"*40,
                after_commit="b"*40, test_id="tests/test_bug.py::test_repro",
                before=before, after=after, execution_id="sandbox-job-1")
    data.update(changes)
    return DifferentialRecord(**data)


def test_verified_transition_is_narrowly_scoped():
    decision = assess_differential(case())
    assert decision.status == "REGRESSION_OBSERVED"
    assert "limited to this test" in decision.explanation


def test_errors_and_skips_cannot_count_as_repair():
    for status in ("ERROR", "SKIP", "TIMEOUT", "UNKNOWN"):
        assert assess_differential(case(status, "PASS")).status == "INCONCLUSIVE"
        assert assess_differential(case("ASSERT_FAIL", status)).status == "INCONCLUSIVE"


def test_no_failure_before_fix_is_not_regression_proof():
    assert assess_differential(case("PASS", "PASS")).status == "NOT_DEMONSTRATED"


def test_fix_that_still_fails_is_rejected():
    assert assess_differential(case("ASSERT_FAIL", "ASSERT_FAIL")).status == "FIX_FAILS"


def test_identical_revisions_not_qualified():
    assert assess_differential(case(after_commit="a"*40)).status == "INCONCLUSIVE"


def test_missing_execution_identity_fails_closed():
    assert assess_differential(case(execution_id="")).status == "INCONCLUSIVE"


def test_fake_status_never_qualifies():
    assert assess_differential(case("FAIL", "PASS")).status == "INCONCLUSIVE"
