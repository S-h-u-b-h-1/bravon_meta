import json
from pathlib import Path

from proofops.hackathon_eval import evaluate_meta_evidence


ROOT = Path(__file__).resolve().parents[1]


def test_actual_meta_evidence_metrics_are_reproducible(tmp_path):
    output = tmp_path / "meta-evaluation.json"
    report = evaluate_meta_evidence(
        evidence_root=ROOT / "docs" / "evidence",
        output=output,
    )
    assert json.loads(output.read_text(encoding="utf-8")) == report
    assert report["runs"] == 9
    assert report["root_cause_accuracy"] == 1
    assert report["repair_success_rate"] == 4 / 6
    assert report["false_green_proposals_rejected"] == 2
    assert report["false_repair_acceptance_rate"] == 0
    assert report["abstention_quality"] == 0
    assert report["evidence_coverage"] == 1
    assert report["end_to_end_runs"] == 3
    assert set(report["end_to_end_by_case_ms"]) == {
        "software-refund-negative-quantity",
        "data-final-row-and-decimals",
        "infrastructure-healthcheck-hardening",
    }
    assert report["end_to_end_execution_ms"] == sum(report["end_to_end_by_case_ms"].values())
    assert report["model_requests"] == 45
    assert report["input_tokens"] == 16_199
    assert report["output_tokens"] == 1_791
    assert report["cost_usd"] == 0


def test_timed_runs_cover_the_full_recorded_pipeline():
    paths = sorted((ROOT / "docs" / "evidence").glob("local-meta-timed-*.json"))
    assert len(paths) == 3
    for path in paths:
        run = json.loads(path.read_text(encoding="utf-8"))
        investigation = run["investigation"]
        assert run["pipeline_duration_ms"] == (
            investigation["reproduction_ms"]
            + investigation["duration_ms"]
            + run["verification"]["duration_ms"]
        )
