from pathlib import Path

import pytest

from tripwire.demo.fraud import (
    DEFAULT_MODEL_ARTIFACT,
    DemoBuild,
    DeterministicFraudModel,
    build_demo_world,
    load_model_artifact,
)
from tripwire.domain import AgentAction, AgentDecision
from tripwire.provenance import sha256_file

DEMO_DIR = Path("demo/fraud")


def _decision(build: DemoBuild, transaction_id: str) -> AgentDecision:
    return next(item for item in build.decisions if item.transaction_id == transaction_id)


def test_baseline_is_byte_stable() -> None:
    first = build_demo_world(demo_dir=DEMO_DIR)
    second = build_demo_world(demo_dir=DEMO_DIR)

    assert first.output_hash == second.output_hash
    assert first.features == second.features
    assert first.predictions == second.predictions
    assert first.decisions == second.decisions
    assert first.model_artifact_hash == sha256_file(DEFAULT_MODEL_ARTIFACT)


def test_model_executes_the_versioned_logistic_artifact() -> None:
    artifact = load_model_artifact()
    model = DeterministicFraudModel()
    prediction = model.predict(
        {
            "transaction_id": "artifact-proof",
            "fraud_signal": 0.62,
            "amount_usd": 520.0,
            "is_international": True,
            "merchant_risk": "medium",
            "device_age_days": None,
            "chargeback_count_30d": 0,
        }
    )

    assert artifact.model_family == "logistic_regression"
    assert prediction.probability == pytest.approx(0.669)
    assert prediction.model_version == artifact.model_version
    assert prediction.model_artifact_hash == sha256_file(DEFAULT_MODEL_ARTIFACT)


def test_semantic_regression_changes_real_model_and_agent_behavior() -> None:
    baseline = build_demo_world(demo_dir=DEMO_DIR, scenario="baseline")
    candidate = build_demo_world(demo_dir=DEMO_DIR, scenario="unsafe_semantic")

    before = _decision(baseline, "TX-009")
    after = _decision(candidate, "TX-009")

    assert before.model_result.probability == pytest.approx(0.669)
    assert after.model_result.probability == pytest.approx(0.498)
    assert before.action is AgentAction.REVIEW
    assert after.action is AgentAction.APPROVE


def test_distinct_related_change_hits_the_same_behavioral_boundary() -> None:
    baseline = build_demo_world(demo_dir=DEMO_DIR, scenario="baseline")
    related = build_demo_world(demo_dir=DEMO_DIR, scenario="unsafe_related")

    before = _decision(baseline, "TX-009")
    after = _decision(related, "TX-009")

    assert before.action is AgentAction.REVIEW
    assert after.action is AgentAction.APPROVE


def test_safe_addition_does_not_change_model_or_agent_behavior() -> None:
    baseline = build_demo_world(demo_dir=DEMO_DIR, scenario="baseline")
    candidate = build_demo_world(demo_dir=DEMO_DIR, scenario="safe_additive")

    assert baseline.predictions == candidate.predictions
    assert baseline.decisions == candidate.decisions


def test_mechanical_break_fails_at_the_real_model_contract() -> None:
    with pytest.raises(KeyError, match="fraud_signal"):
        build_demo_world(demo_dir=DEMO_DIR, scenario="unsafe_mechanical")
