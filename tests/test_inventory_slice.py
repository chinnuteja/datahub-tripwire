"""The evaluator must be domain-neutral, not fraud-specific.

These tests run a second vertical slice — different input schema, different pinned model
artifact, different downstream agent, different defect class — through the same
AssessmentService that serves the fraud slice. No evaluator code is duplicated for it.
"""

from datetime import UTC, datetime
from pathlib import Path

from tripwire.application import AssessmentService
from tripwire.demo.fraud import FRAUD_SLICE
from tripwire.demo.inventory import INVENTORY_SLICE
from tripwire.domain import (
    ContextCoverage,
    CoverageStatus,
    EntityKind,
    EntityRef,
    LineagePath,
    Verdict,
)
from tripwire.ports import ContextSnapshot

DEMO = Path("demo/inventory")

ROOT = EntityRef(
    urn=(
        "urn:li:dataset:(urn:li:dataPlatform:duckdb,"
        "tripwire_inventory.supply.fct_inventory_features,PROD)"
    ),
    kind=EntityKind.DATASET,
    display_name="inventory features",
)
MODEL = EntityRef(
    urn="urn:li:mlModel:(urn:li:dataPlatform:tripwire,stockout_risk_classifier,PROD)",
    kind=EntityKind.ML_MODEL,
    display_name="Stockout Risk Classifier",
)
AGENT = EntityRef(
    urn=(
        "urn:li:dataJob:(urn:li:dataFlow:(tripwire,tripwire_inventory_agents,PROD),"
        "replenishment_agent)"
    ),
    kind=EntityKind.DATA_JOB,
    display_name="Replenishment Agent",
)


def context() -> ContextSnapshot:
    return ContextSnapshot(
        root=ROOT,
        facts=(),
        paths=(LineagePath(nodes=(ROOT, MODEL)), LineagePath(nodes=(ROOT, AGENT))),
        coverage=ContextCoverage(
            status=CoverageStatus.COMPLETE,
            required_operations=("get_entities", "get_lineage", "list_schema_fields"),
            completed_operations=("get_entities", "get_lineage", "list_schema_fields"),
            critical_consumers=(MODEL, AGENT),
        ),
        provider="recorded-test-context",
    )


def service() -> AssessmentService:
    return AssessmentService(root=Path.cwd(), demo_dir=DEMO, spec=INVENTORY_SLICE)


def test_second_slice_declares_its_own_model_agent_and_schema() -> None:
    assert INVENTORY_SLICE.name != FRAUD_SLICE.name
    assert INVENTORY_SLICE.key == "sku_id"
    assert INVENTORY_SLICE.table == "raw_inventory"
    assert INVENTORY_SLICE.artifact_path != FRAUD_SLICE.artifact_path
    assert INVENTORY_SLICE.agent_version != FRAUD_SLICE.agent_version


def test_backorder_cap_regression_is_unsafe_with_a_minimized_witness() -> None:
    passport = service().assess(candidate="unsafe_backorder_cap", context=context())

    assert passport.verdict is Verdict.UNSAFE
    assert passport.counterexample is not None

    witness = passport.counterexample
    observations = passport.evaluations[0].observations
    assert observations["model_version"] == "stockout-risk-classifier/1.0.0"
    assert observations["replayed_rows"] == 10
    assert witness.baseline["agent_version"] == "replenishment-agent/1.0.0"
    # The regression only ever lowers apparent risk, which is the dangerous direction.
    assert (
        witness.candidate["model_result"]["probability"]
        < witness.baseline["model_result"]["probability"]
    )
    assert witness.minimization_attempts > 0


def test_identical_sql_is_safe_within_scope_for_the_second_slice() -> None:
    passport = service().assess(candidate="baseline", context=context())

    assert passport.verdict is Verdict.SAFE_WITHIN_SCOPE
    assert passport.counterexample is None
    assert all(result.status.value == "passed" for result in passport.evaluations)
    assert f"{INVENTORY_SLICE.name} vertical slice" in " ".join(passport.limitations)


def test_fraud_slice_is_unaffected_by_the_second_slice_existing() -> None:
    """Registering a second slice must not perturb the published fraud evidence."""

    started = datetime.now(UTC)
    fraud = AssessmentService(root=Path.cwd(), demo_dir=Path("demo/fraud"))
    passport = fraud.assess(candidate="unsafe_semantic", context=_fraud_context())

    assert passport.verdict is Verdict.UNSAFE
    assert passport.counterexample is not None
    assert passport.counterexample.transaction["transaction_id"] == "TX-009"
    assert passport.evaluations[0].observations["model_version"] == (
        "fraud-risk-calibrator/2.0.0"
    )
    assert passport.run.created_at >= started


def _fraud_context() -> ContextSnapshot:
    root = EntityRef(
        urn=(
            "urn:li:dataset:(urn:li:dataPlatform:duckdb,"
            "tripwire_fraud.fraud.fct_fraud_features,PROD)"
        ),
        kind=EntityKind.DATASET,
        display_name="fraud features",
    )
    model = EntityRef(
        urn="urn:li:mlModel:(urn:li:dataPlatform:tripwire,fraud_logistic_rule,PROD)",
        kind=EntityKind.ML_MODEL,
        display_name="Fraud Logistic Rule",
    )
    agent = EntityRef(
        urn=(
            "urn:li:dataJob:(urn:li:dataFlow:(tripwire,tripwire_fraud_agents,PROD),"
            "fraud_review_agent)"
        ),
        kind=EntityKind.DATA_JOB,
        display_name="Fraud Review Agent",
    )
    return ContextSnapshot(
        root=root,
        facts=(),
        paths=(LineagePath(nodes=(root, model)), LineagePath(nodes=(root, agent))),
        coverage=ContextCoverage(
            status=CoverageStatus.COMPLETE,
            required_operations=("get_entities", "get_lineage", "list_schema_fields"),
            completed_operations=("get_entities", "get_lineage", "list_schema_fields"),
            critical_consumers=(model, agent),
        ),
        provider="recorded-test-context",
    )
