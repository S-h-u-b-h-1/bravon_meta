"""Deterministic Bravon false-green verification benchmark.

No model calls, file writes, external requests or code execution. This is a
small fixture smoke-test, NOT evidence of performance on real repositories.
"""
from __future__ import annotations

import argparse
import json

from bravon_verification import Invariant, Observation, Verdict, verify_repair


CASES = (
    ("true_repair", {"original": True, "boundary": True, "accounting": 100}, Verdict.VERIFIED),
    ("false_green_boundary", {"original": True, "boundary": False, "accounting": 100}, Verdict.CONTRADICTED),
    ("false_green_accounting", {"original": True, "boundary": True, "accounting": 99}, Verdict.CONTRADICTED),
    ("failed_original", {"original": False, "boundary": True, "accounting": 100}, Verdict.CONTRADICTED),
    ("missing_observation", {"original": True, "boundary": True}, Verdict.INSUFFICIENT_EVIDENCE),
)
RULES = (
    Invariant("original", "eq", True, "e-original"),
    Invariant("boundary", "eq", True, "e-boundary"),
    Invariant("accounting", "eq", 100, "e-accounting"),
)


def evaluate_cases() -> dict:
    entries = []
    for name, values, expected in CASES:
        observations = tuple(
            Observation("e-" + key, key, value, "fixture-oracle", "fixture-v1")
            for key, value in values.items()
        )
        result = verify_repair(
            RULES, observations, expected_environment="fixture-v1",
            trusted_sources=frozenset({"fixture-oracle"}),
        )
        entries.append({
            "case": name,
            "expected": expected.value,
            "actual": result.verdict.value,
            "correct": result.verdict == expected,
            "checks": [{"key": c.key, "status": c.status} for c in result.checks],
        })
    # Weak comparator: trust the original test alone.
    baseline_predictions = {
        name: (Verdict.VERIFIED if values.get("original") is True else Verdict.CONTRADICTED)
        for name, values, _ in CASES
    }
    baseline_correct = sum(
        baseline_predictions[name] == expected for name, _, expected in CASES
    )
    baseline_false_verified = sum(
        baseline_predictions[name] == Verdict.VERIFIED and expected != Verdict.VERIFIED
        for name, _, expected in CASES
    )
    count = sum(e["correct"] for e in entries)
    return {
        "schema": "bravon.false-green-smoke.v1",
        "disclaimer": "Deterministic authored fixtures only; not a real-world accuracy estimate.",
        "total": len(entries),
        "correct": count,
        "baseline": {"correct": baseline_correct, "false_verified": baseline_false_verified},
        "false_verified": sum(
            e["actual"] == Verdict.VERIFIED.value and e["expected"] != Verdict.VERIFIED.value
            for e in entries
        ),
        "cases": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = evaluate_cases()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Bravon fixture benchmark: {result['correct']}/{result['total']} expected outcomes; "
              f"false verified: {result['false_verified']}")
    return 0 if result["correct"] == result["total"] and result["false_verified"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
