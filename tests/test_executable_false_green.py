"""Executed fixture: green narrow test can conceal a faulty refund implementation.

Pure, locally constructed functions only. No untrusted repository code or shell.
"""
from bravon_verification import Invariant, Observation, Verdict, verify_repair


def correct_refund(qty: int, unit_price: int) -> int:
    if type(qty) is not int or qty < 0:
        raise ValueError("invalid quantity")
    return qty * unit_price


def faulty_refund(qty: int, unit_price: int) -> int:
    # Deliberate defect: accepts negative quantities.
    return qty * unit_price


def _rejects_negative(fn) -> bool:
    try:
        fn(-1, 100)
    except ValueError:
        return True
    return False


def check_implementation(fn):
    checks = {
        "original": fn(2, 50) == 100,
        "reject_negative": _rejects_negative(fn),
        "zero": fn(0, 50) == 0,
    }
    obs = tuple(
        Observation("e-" + name, name, value, "executable-fixture", "refund-fixture-v1")
        for name, value in checks.items()
    )
    invariants = tuple(
        Invariant(name, "eq", True, "e-" + name) for name in checks
    )
    result = verify_repair(
        invariants, obs,
        expected_environment="refund-fixture-v1",
        trusted_sources=frozenset({"executable-fixture"}),
    )
    return checks, result.verdict


def test_narrow_green_but_broken_behavior_is_rejected():
    checks, verdict = check_implementation(faulty_refund)
    assert checks["original"] is True
    assert checks["reject_negative"] is False
    assert verdict == Verdict.CONTRADICTED


def test_correct_implementation_qualifies_on_fixture():
    checks, verdict = check_implementation(correct_refund)
    assert all(checks.values())
    assert verdict == Verdict.VERIFIED
