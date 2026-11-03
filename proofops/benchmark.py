"""Small repeatability benchmark for the deterministic lab (NOT an AI accuracy test).

Usage: python -m proofops.benchmark --repeats 10 --output proofops-benchmark.json
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from .core import IncidentLab, SCENARIOS
from .probes import is_healthy, check_all


def run_benchmark(repeats: int = 10) -> dict:
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    lab = IncidentLab()
    results = []
    for _ in range(repeats):
        for scenario in SCENARIOS:
            start = perf_counter()
            incident = lab.inject(scenario)
            failed_before = not is_healthy(check_all(lab.config))
            lab.analyze(incident.id)
            lab.verify(incident.id)
            verification_passed = bool(incident.verification and incident.verification.success)
            if verification_passed:
                lab.execute(incident.id, approved=True, expected_revision=lab.revision)
            recovered = is_healthy(check_all(lab.config)) and incident.status == "recovered"
            results.append({
                "scenario": scenario,
                "initial_failure_detected": failed_before,
                "sandbox_checks_passed": verification_passed,
                "recovered": recovered,
                "action": incident.diagnosis.action if incident.diagnosis else None,
                "engine": incident.diagnosis.source if incident.diagnosis else None,
                "elapsed_ms": round(1000 * (perf_counter() - start), 3),
            })
    return {
        "name": "ProofOps deterministic simulation acceptance test",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "in-memory state machine, synthetic service topology, no actual network or LLM inference",
        "is_ai_benchmark": False,
        "runs": len(results),
        "all_passed": all(r["initial_failure_detected"] and r["sandbox_checks_passed"] and r["recovered"] for r in results),
        "successes": sum(r["recovered"] for r in results),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=10, help="Iterations per failure scenario")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path")
    args = parser.parse_args()
    result = run_benchmark(args.repeats)
    print(f"{result['successes']}/{result['runs']} recovered in a synthetic state-machine benchmark")
    print("This does NOT measure Muse or real network reliability.")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(f"Evidence written to {args.output}")
    if not result["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
