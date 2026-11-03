import json
from pathlib import Path

import pytest

from proofops.hackathon_investigation import (
    InvalidInvestigation,
    ScriptedRepairProvider,
    investigate_case,
)
from proofops.hackathon_worker import load_cases, verify_candidate


ROOT = Path(__file__).resolve().parents[1]


def test_investigation_uses_bounded_tools_and_never_exposes_hidden_test():
    case = load_cases(ROOT / "fixtures" / "hackathon")["software-refund-negative-quantity"]
    provider = ScriptedRepairProvider([
        {"kind": "tool", "name": "read_target", "arguments": {}},
        {"kind": "tool", "name": "read_failure", "arguments": {}},
        {
            "kind": "final",
            "decision": "propose",
            "root_cause": "Negative quantities are multiplied without validation.",
            "replacement": (case.root / "complete.py").read_text(encoding="utf-8"),
            "rationale": "Reject every negative quantity before multiplication.",
            "uncertainty": "Only the supplied public regression was observed.",
            "evidence_ids": ["source", "failure"],
            "confidence": 0.84,
        },
    ])
    result = investigate_case(case, provider)
    assert result.proposal is not None
    assert result.reproduction_ms > 0
    assert result.proposal.target_file == "refund.py"
    assert [step["kind"] for step in result.transcript] == ["tool", "tool", "final"]
    serialized = json.dumps(provider.requests)
    assert "test_behavior.py" not in serialized
    assert "all_negative_quantities" not in serialized


def test_investigation_cannot_propose_before_source_and_failure_evidence():
    case = load_cases(ROOT / "fixtures" / "hackathon")["software-refund-negative-quantity"]
    provider = ScriptedRepairProvider([{
        "kind": "final", "decision": "propose", "root_cause": "Guess",
        "replacement": (case.root / "complete.py").read_text(encoding="utf-8"),
        "rationale": "Guess", "uncertainty": "High",
        "evidence_ids": [], "confidence": 0.2,
    }])
    with pytest.raises(InvalidInvestigation):
        investigate_case(case, provider)


def test_ai_confidence_cannot_override_false_green_rejection():
    case = load_cases(ROOT / "fixtures" / "hackathon")["data-final-row-and-decimals"]
    provider = ScriptedRepairProvider([
        {"kind": "tool", "name": "read_target", "arguments": {}},
        {"kind": "tool", "name": "read_failure", "arguments": {}},
        {
            "kind": "final", "decision": "propose",
            "root_cause": "The final row is skipped.",
            "replacement": (case.root / "incomplete.py").read_text(encoding="utf-8"),
            "rationale": "Sum every row after converting values to integers.",
            "uncertainty": "Decimal behavior was not observed.",
            "evidence_ids": ["source", "failure"], "confidence": 0.99,
        },
    ])
    result = investigate_case(case, provider)
    report = verify_candidate(case, result.proposal)
    assert result.confidence == 0.99
    assert report.verdict == "REJECTED_FALSE_GREEN"
