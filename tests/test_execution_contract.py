from dataclasses import replace
from bravon_execution_contract import ExecutionManifest, assess_execution

BASE = ExecutionManifest(
    repository="example/library", before_commit="a"*40, after_commit="b"*40,
    test_id="tests/test_bug.py::test_regression", execution_id="job-42",
    runner_id="runner-7", image_digest="sha256:" + "c"*64,
    before_run_id="before-42", after_run_id="after-42",
    before_status="ASSERT_FAIL", after_status="PASS",
)


def test_valid_execution_manifest_only_records_narrow_regression():
    assert assess_execution(BASE).status == "REGRESSION_OBSERVED"


def test_image_tag_instead_of_immutable_digest_rejected():
    assert assess_execution(replace(BASE, image_digest="python:3.12")).status == "INCONCLUSIVE"


def test_missing_runner_rejected():
    assert assess_execution(replace(BASE, runner_id="")).status == "INCONCLUSIVE"


def test_same_execution_for_both_versions_rejected():
    assert assess_execution(replace(BASE, after_run_id=BASE.before_run_id)).status == "INCONCLUSIVE"


def test_short_commit_rejected():
    assert assess_execution(replace(BASE, before_commit="abc1234")).status == "INCONCLUSIVE"


def test_timeout_cannot_be_reported_as_success():
    assert assess_execution(replace(BASE, before_status="TIMEOUT")).status == "INCONCLUSIVE"
