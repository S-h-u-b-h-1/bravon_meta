import json
from pathlib import Path

from proofops.hackathon_eval import run_evaluation


ROOT = Path(__file__).resolve().parents[1]


def test_evaluation_records_real_results_without_claiming_ai(tmp_path):
    output = tmp_path / "evaluation.json"
    report = run_evaluation(
        fixtures=ROOT / "fixtures" / "hackathon",
        output=output,
        signing_key=b"evaluation-key-that-is-at-least-32-bytes",
    )
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved == report
    assert report["execution"]["cases"] == 6
    assert report["execution"]["verified_repairs"] == 3
    assert report["execution"]["incomplete_repairs_rejected"] == 3
    assert report["execution"]["false_repair_acceptance_rate"] == 0
    assert report["meta_inference"] == {
        "status": "NOT_RUN",
        "model": None,
        "requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0,
    }
    assert all(item["evidence_envelope"]["signature"] for item in report["results"])
