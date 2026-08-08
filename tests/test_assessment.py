from datetime import UTC, datetime
from pathlib import Path

from tripwire.application import AssessmentService
from tripwire.change import analyze_sql_change
from tripwire.domain import (
    ChangeFactKind,
    ContextAuthority,
    ContextCoverage,
    ContextFact,
    CoverageGap,
    CoverageStatus,
    EntityKind,
    EntityRef,
    LineagePath,
    ProtectionStatus,
    Verdict,
)
from tripwire.memory import approve_protection
from tripwire.ports import ContextSnapshot, RuntimeUnavailableError

ROOT = EntityRef(
    urn=(
        "urn:li:dataset:(urn:li:dataPlatform:duckdb,"
        "tripwire_fraud.fraud.fct_fraud_features,PROD)"
    ),
    kind=EntityKind.DATASET,
    display_name="fraud features",
)
MODEL = EntityRef(
    urn="urn:li:mlModel:(urn:li:dataPlatform:tripwire,fraud_logistic_rule,PROD)",
    kind=EntityKind.ML_MODEL,
    display_name="Fraud Logistic Rule",
)
AGENT = EntityRef(
    urn=(
        "urn:li:dataJob:(urn:li:dataFlow:(tripwire,tripwire_fraud_agents,PROD),"
        "fraud_review_agent)"
    ),
    kind=EntityKind.DATA_JOB,
    display_name="Fraud Review Agent",
)


def complete_context(*, protections: tuple = (), facts: tuple = ()) -> ContextSnapshot:
    return ContextSnapshot(
        root=ROOT,
        facts=facts,
        paths=(LineagePath(nodes=(ROOT, MODEL)), LineagePath(nodes=(ROOT, AGENT))),
        coverage=ContextCoverage(
            status=CoverageStatus.COMPLETE,
            required_operations=("get_entities", "get_lineage", "list_schema_fields"),
            completed_operations=("get_entities", "get_lineage", "list_schema_fields"),
            critical_consumers=(MODEL, AGENT),
        ),
        provider="recorded-test-context",
        protections=protections,
    )


def incomplete_context() -> ContextSnapshot:
    return ContextSnapshot(
        root=ROOT,
        facts=(),
        paths=(),
        coverage=ContextCoverage(
            status=CoverageStatus.INCOMPLETE,
            required_operations=("get_entities", "get_lineage", "list_schema_fields"),
            completed_operations=("get_entities", "list_schema_fields"),
            gaps=(
                CoverageGap(
                    code="LINEAGE_UNAVAILABLE",
                    message="Downstream lineage could not be retrieved.",
                    entity_urn=ROOT.urn,
                    operation="get_lineage",
                ),
            ),
        ),
        provider="recorded-test-context",
    )


def service() -> AssessmentService:
    return AssessmentService(root=Path.cwd(), demo_dir=Path("demo/fraud"))


def test_semantic_regression_is_unsafe_with_agent_boundary_witness() -> None:
    passport = service().assess(candidate="unsafe_semantic", context=complete_context())

    assert passport.verdict is Verdict.UNSAFE
    assert passport.counterexample is not None
    assert passport.counterexample.transaction["transaction_id"] == "TX-009"
    assert passport.counterexample.baseline["action"] == "review"
    assert passport.counterexample.candidate["action"] == "approve"
    assert passport.proposed_protection is not None
    assert passport.proposed_protection.status is ProtectionStatus.PROPOSED
    assert {result.kind.value for result in passport.evaluations} == {"model", "agent"}


def test_additive_change_is_safe_within_explicit_scope() -> None:
    passport = service().assess(candidate="safe_additive", context=complete_context())

    assert passport.verdict is Verdict.SAFE_WITHIN_SCOPE
    assert passport.counterexample is None
    assert passport.proposed_protection is None
    assert all(result.status.value == "passed" for result in passport.evaluations)
    assert passport.scope_accounting is not None
    assert passport.scope_accounting.completed_operations == 3
    assert passport.scope_accounting.required_operations == 3
    assert passport.scope_accounting.critical_consumers_evaluated == 2
    assert passport.scope_accounting.critical_consumers_discovered == 2
    assert passport.scope_accounting.lineage_frontier_complete


def test_mechanical_break_is_unsafe_with_executed_error_evidence() -> None:
    passport = service().assess(candidate="unsafe_mechanical", context=complete_context())

    assert passport.verdict is Verdict.UNSAFE
    assert passport.reason_codes == ("CANDIDATE_EXECUTION_FAILED",)
    assert passport.counterexample is None
    assert all(result.observations["error_type"] == "KeyError" for result in passport.evaluations)


def test_missing_lineage_can_never_be_called_safe() -> None:
    passport = service().assess(candidate="safe_additive", context=incomplete_context())

    assert passport.verdict is Verdict.UNVERIFIED
    assert passport.reason_codes == ("NO_CRITICAL_CONSUMER_EVALUATED",)


def test_related_change_is_caught_by_human_approved_learned_protection() -> None:
    first = service().assess(candidate="unsafe_semantic", context=complete_context())
    active = approve_protection(
        first,
        approved_by="urn:li:corpuser:fraud-platform",
    )

    second = service().assess(
        candidate="unsafe_related",
        context=complete_context(protections=(active,)),
    )

    assert second.verdict is Verdict.UNSAFE
    assert second.reason_codes == ("LEARNED_PROTECTION_VIOLATED",)
    assert second.applied_protections == (active,)
    assert second.proposed_protection is None
    learned = next(result for result in second.evaluations if result.kind.value == "protection")
    assert learned.status.value == "failed"
    assert learned.observations["protection_id"] == active.protection_id
    assert learned.observations["transaction_id"] == "TX-009"


def test_git_loaded_sql_and_change_facts_drive_the_same_evidence_engine() -> None:
    baseline = Path("demo/fraud/sql/baseline.sql").read_text(encoding="utf-8")
    candidate = Path("demo/fraud/sql/unsafe_semantic.sql").read_text(encoding="utf-8")
    facts = analyze_sql_change(baseline, candidate)

    passport = service().assess(
        candidate="git-change",
        context=complete_context(),
        base_revision="a" * 40,
        candidate_revision="b" * 40,
        changed_path="demo/fraud/models/fct_fraud_features.sql",
        resolved_entity=ROOT,
        change_facts=facts,
        baseline_sql=baseline,
        candidate_sql=candidate,
    )

    assert passport.verdict is Verdict.UNSAFE
    assert passport.change.base_revision == "a" * 40
    assert passport.change.candidate_revision == "b" * 40
    assert passport.change.changed_paths == ("demo/fraud/models/fct_fraud_features.sql",)
    assert passport.resolved_entity == ROOT
    assert passport.change_facts == facts
    assert any(fact.kind is ChangeFactKind.NULL_HANDLING for fact in passport.change_facts)
    assert passport.remediation is not None
    assert passport.remediation.status.value == "verified"
    assert passport.remediation.restored_evaluations == ("model-1", "agent-2")
    assert "COALESCE(device_age_days, 0)" in passport.remediation.patch


def test_datahub_ownership_routes_required_reviewers() -> None:
    fact = ContextFact(
        fact_type="mcp.get_entities",
        subject=ROOT,
        value={
            "result": {
                "urn": ROOT.urn,
                "ownership": {
                    "owners": [
                        {
                            "owner": {
                                "urn": "urn:li:corpuser:fraud-platform",
                                "properties": {
                                    "displayName": "Fraud Platform Team",
                                    "email": "fraud-platform@example.invalid",
                                },
                            }
                        }
                    ]
                },
            }
        },
        authority=ContextAuthority.DATAHUB_MCP,
        operation="get_entities",
        retrieved_at=datetime.now(UTC),
        source_hash="a" * 64,
    )

    passport = service().assess(
        candidate="safe_additive",
        context=complete_context(facts=(fact,)),
    )

    assert len(passport.owner_routes) == 1
    assert passport.owner_routes[0].owner_urn == "urn:li:corpuser:fraud-platform"
    assert passport.owner_routes[0].source_entity_urn == ROOT.urn


def test_learned_protection_executes_its_stored_fixture_not_seed_lookup() -> None:
    first = service().assess(candidate="unsafe_semantic", context=complete_context())
    active = approve_protection(first, approved_by="urn:li:corpuser:fraud-platform")
    portable_fixture = {**active.fixture, "transaction_id": "NOT-IN-SEED"}
    active = active.model_copy(update={"fixture": portable_fixture})

    second = service().assess(
        candidate="unsafe_related",
        context=complete_context(protections=(active,)),
    )

    learned = next(result for result in second.evaluations if result.kind.value == "protection")
    assert learned.status.value == "failed"
    assert learned.observations["transaction_id"] == "NOT-IN-SEED"
    assert learned.observations["fixture_hash"]


def test_runtime_outage_is_unverified_not_an_unsafe_code_claim(monkeypatch) -> None:
    from tripwire.demo.fraud import build_demo_world as real_build

    def unavailable(*, demo_dir: Path, scenario: str):
        if scenario == "safe_additive":
            raise RuntimeUnavailableError("DuckDB worker is unavailable")
        return real_build(demo_dir=demo_dir, scenario=scenario)

    monkeypatch.setattr("tripwire.application.assessment.build_demo_world", unavailable)

    passport = service().assess(candidate="safe_additive", context=complete_context())

    assert passport.verdict is Verdict.UNVERIFIED
    assert passport.reason_codes == ("CRITICAL_EVALUATION_INCOMPLETE",)
    assert all(result.status.value == "error" for result in passport.evaluations)
    assert all(
        result.observations["failure_class"] == "runtime_unavailable"
        for result in passport.evaluations
    )


def test_datahub_graph_consumers_compile_the_evaluation_plan() -> None:
    model_only = ContextSnapshot(
        root=ROOT,
        facts=(),
        paths=(LineagePath(nodes=(ROOT, MODEL)),),
        coverage=ContextCoverage(
            status=CoverageStatus.COMPLETE,
            required_operations=("get_entities", "get_lineage", "list_schema_fields"),
            completed_operations=("get_entities", "get_lineage", "list_schema_fields"),
            critical_consumers=(MODEL,),
        ),
        provider="mutated-datahub-context",
    )

    passport = service().assess(candidate="safe_additive", context=model_only)

    assert len(passport.evaluations) == 1
    assert passport.evaluations[0].kind.value == "model"
    assert all(result.consumer != AGENT for result in passport.evaluations)
