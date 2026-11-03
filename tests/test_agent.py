import pytest

from proofops.agent import diagnose, evidence_diagnosis
from proofops.domain import LabConfig
from proofops.probes import check_all


class GoodModel:
    def analyze(self, config, checks, permitted_action):
        return {
            "summary": "Synthetic DNS drift", "root_cause": "Unexpected record",
            "reasoning": "The measured DNS invariant failed", "action": permitted_action,
            "evidence_ids": ["dns-record"], "confidence": 0.91,
        }


class UnsafeModel:
    def analyze(self, config, checks, permitted_action):
        return {
            "summary": "bad", "root_cause": "bad", "reasoning": "bad",
            "action": "run_arbitrary_command", "evidence_ids": ["dns-record"],
        }


class FakeEvidenceModel:
    def analyze(self, config, checks, permitted_action):
        return {
            "summary": "bad", "root_cause": "bad", "reasoning": "bad",
            "action": permitted_action, "evidence_ids": ["not-observed"],
        }


class BrokenModel:
    def analyze(self, config, checks, permitted_action):
        raise TimeoutError("No response")


def data():
    config = LabConfig(dns_record="unknown")
    return config, check_all(config)


def test_valid_meta_analysis_is_advisory_only():
    cfg, checks = data()
    result = diagnose(cfg, checks, use_meta=True, provider=GoodModel())
    assert result.source == "meta-muse"
    assert result.action == "restore_dns"
    assert cfg.dns_record == "unknown"


@pytest.mark.parametrize("provider", [UnsafeModel(), FakeEvidenceModel(), BrokenModel()])
def test_invalid_meta_output_falls_back_to_measured_evidence(provider):
    cfg, checks = data()
    result = diagnose(cfg, checks, use_meta=True, provider=provider)
    assert result.source == "evidence-engine"
    assert result.action == "restore_dns"
    assert "fell back" in result.model_note


def test_no_model_invoked_when_opt_out():
    cfg, checks = data()
    result = diagnose(cfg, checks, use_meta=False, provider=BrokenModel())
    assert result.source == "evidence-engine"
    assert "no AI model invoked" in result.model_note


def test_no_safe_action_on_healthy_state():
    with pytest.raises(ValueError, match="No safe"):
        evidence_diagnosis(LabConfig(), check_all(LabConfig()))
