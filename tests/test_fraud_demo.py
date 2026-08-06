from pathlib import Path

import pytest

from tripwire.demo.fraud import DemoBuild, build_demo_world
from tripwire.domain import AgentAction, AgentDecision

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
