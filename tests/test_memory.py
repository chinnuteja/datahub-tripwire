from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from tripwire.application import AssessmentService
from tripwire.config import TripwireSettings
from tripwire.domain import (
    ContextCoverage,
    CoverageStatus,
    EntityKind,
    EntityRef,
    LineagePath,
    ProtectionStatus,
)
from tripwire.memory import (
    DataHubMemoryStore,
    approve_protection,
    write_memory_receipt,
    write_protection,
)
from tripwire.ports import ContextSnapshot
from tripwire.providers.datahub_mcp import _active_protection

ROOT = EntityRef(
    urn=(
        "urn:li:dataset:(urn:li:dataPlatform:duckdb,"
        "tripwire_fraud.fraud.fct_fraud_features,PROD)"
    ),
    kind=EntityKind.DATASET,
    display_name="Fraud Features",
)
MODEL = EntityRef(
    urn="urn:li:mlModel:(urn:li:dataPlatform:tripwire,fraud_logistic_rule,PROD)",
    kind=EntityKind.ML_MODEL,
    display_name="Fraud Logistic Rule",
)


def _proposal_passport():
    context = ContextSnapshot(
        root=ROOT,
        facts=(),
        paths=(LineagePath(nodes=(ROOT, MODEL)),),
        coverage=ContextCoverage(
            status=CoverageStatus.COMPLETE,
            required_operations=("get_entities", "get_lineage", "list_schema_fields"),
            completed_operations=("get_entities", "get_lineage", "list_schema_fields"),
            critical_consumers=(MODEL,),
        ),
        provider="recorded-test-context",
    )
    return AssessmentService(root=Path.cwd(), demo_dir=Path("demo/fraud")).assess(
        candidate="unsafe_semantic",
        context=context,
    )


def test_approval_records_exact_human_and_timestamp() -> None:
    approved_at = datetime(2026, 8, 6, 0, 0, tzinfo=UTC)
    active = approve_protection(
        _proposal_passport(),
        approved_by="urn:li:corpuser:fraud-platform",
        approved_at=approved_at,
    )

    assert active.status is ProtectionStatus.ACTIVE
    assert active.approved_by == "urn:li:corpuser:fraud-platform"
    assert active.approved_at == approved_at


def test_approval_rejects_non_datahub_identity() -> None:
    with pytest.raises(ValueError, match="corpuser URN"):
        approve_protection(_proposal_passport(), approved_by="someone")


def test_live_mcp_payload_parser_returns_only_active_typed_memory() -> None:
    active = approve_protection(
        _proposal_passport(),
        approved_by="urn:li:corpuser:fraud-platform",
    )
    payload = {
        "properties": {
            "customProperties": [
                {"key": "tripwire.memory.kind", "value": "protection"},
                {
                    "key": "tripwire.protection.payload",
                    "value": active.model_dump_json(),
                },
            ]
        }
    }

    assert _active_protection(payload) == active


class _FakeTaggable:
    def __init__(self, urn: str):
        self.urn = urn
        self.tags: list[str] = []

    def add_tag(self, tag: str) -> None:
        if tag not in self.tags:
            self.tags.append(tag)


class _FakeEntities:
    def __init__(self, urns: tuple[str, ...]):
        self.items: dict[str, object] = {urn: _FakeTaggable(urn) for urn in urns}

    def upsert(self, entity: Any) -> None:
        self.items[str(entity.urn)] = entity

    def get(self, urn: str) -> object:
        return self.items[urn]


class _FakeClient:
    def __init__(self, urns: tuple[str, ...]):
        self.entities = _FakeEntities(urns)


class _FakeGraph:
    """Capture emitted MCPs so native aspect writes are assertable without a stack."""

    def __init__(self, fail: bool = False):
        self.emitted: list[Any] = []
        self.fail = fail

    def emit_mcp(self, mcp: Any) -> None:
        if self.fail:
            raise RuntimeError("GMS unreachable")
        self.emitted.append(mcp)

    def aspects(self, name: str) -> list[Any]:
        return [
            mcp.aspect for mcp in self.emitted if type(mcp.aspect).__name__ == name
        ]


def _install_fakes(
    monkeypatch: pytest.MonkeyPatch,
    urns: tuple[str, ...],
    *,
    fail_emit: bool = False,
) -> tuple[_FakeClient, _FakeGraph]:
    client = _FakeClient(urns)
    graph = _FakeGraph(fail=fail_emit)
    monkeypatch.setattr("tripwire.memory.datahub.DataHubClient", lambda **_: client)
    monkeypatch.setattr("tripwire.memory.datahub.DataHubGraph", lambda *_a, **_k: graph)
    return client, graph


def test_datahub_memory_publish_is_retrievable_and_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    passport = _proposal_passport()
    approved = approve_protection(
        passport,
        approved_by="urn:li:corpuser:fraud-platform",
        approved_at=datetime(2026, 8, 6, 0, 0, tzinfo=UTC),
    )
    urns = tuple(ref.urn for ref in approved.affected_entities)
    client, _graph = _install_fakes(monkeypatch, urns)
    store = DataHubMemoryStore(TripwireSettings())

    first = store.publish(passport=passport, protection=approved)
    second = store.publish(passport=passport, protection=approved)

    assert first.protection_urn == second.protection_urn
    assert first.passport_urn == second.passport_urn
    assert store.find_active(passport.proposed_protection) == approved
    for urn in urns:
        entity = client.entities.get(urn)
        assert isinstance(entity, _FakeTaggable)
        assert entity.tags == [first.tag_urn]

    protection_path = tmp_path / "protection.json"
    receipt_path = tmp_path / "receipt.json"
    write_protection(approved, protection_path)
    write_memory_receipt(first, receipt_path)
    assert ProtectionStatus.ACTIVE.value in protection_path.read_text(encoding="utf-8")
    assert first.payload_hash in receipt_path.read_text(encoding="utf-8")


def _approved(passport):
    return approve_protection(
        passport,
        approved_by="urn:li:corpuser:fraud-platform",
        approved_at=datetime(2026, 8, 6, 0, 0, tzinfo=UTC),
    )


def test_protection_is_published_as_a_native_datahub_assertion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tripwire must extend DataHub's shipped governance surface, not reinvent it."""

    passport = _proposal_passport()
    approved = _approved(passport)
    _, graph = _install_fakes(
        monkeypatch, tuple(ref.urn for ref in approved.affected_entities)
    )
    receipt = DataHubMemoryStore(TripwireSettings()).publish(
        passport=passport, protection=approved
    )

    assert receipt.assertion_urn == (
        f"urn:li:assertion:tripwire-{approved.protection_id}-v{approved.version}"
    )
    info = graph.aspects("AssertionInfoClass")
    assert len(info) == 1
    assert info[0].type == "CUSTOM"
    assert info[0].customAssertion.type == "TRIPWIRE_PROTECTION"
    assert info[0].customAssertion.entity == ROOT.urn
    assert info[0].description == approved.invariant
    # Human approval provenance survives the translation to a native primitive.
    assert (
        info[0].customProperties["tripwire.protection.approved_by"]
        == "urn:li:corpuser:fraud-platform"
    )


def test_assertion_run_records_the_witness_failure_as_real_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A protection born from a witness records that witness as its first run."""

    passport = _proposal_passport()
    approved = _approved(passport)
    _, graph = _install_fakes(
        monkeypatch, tuple(ref.urn for ref in approved.affected_entities)
    )
    receipt = DataHubMemoryStore(TripwireSettings()).publish(
        passport=passport, protection=approved
    )

    runs = graph.aspects("AssertionRunEventClass")
    assert len(runs) == 1
    assert runs[0].runId == passport.run.run_id
    assert runs[0].assertionUrn == receipt.assertion_urn
    assert runs[0].asserteeUrn == ROOT.urn
    assert runs[0].result.type == "FAILURE"
    assert receipt.assertion_result == "FAILURE"
    assert runs[0].result.nativeResults["tripwire.verdict"] == "UNSAFE"


def test_unsafe_verdict_opens_a_native_incident(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    passport = _proposal_passport()
    approved = _approved(passport)
    _, graph = _install_fakes(
        monkeypatch, tuple(ref.urn for ref in approved.affected_entities)
    )
    receipt = DataHubMemoryStore(TripwireSettings()).publish(
        passport=passport, protection=approved
    )

    incidents = graph.aspects("IncidentInfoClass")
    assert len(incidents) == 1
    assert incidents[0].type == "CUSTOM"
    assert incidents[0].customType == "Tripwire Change Safety"
    assert incidents[0].status.state == "ACTIVE"
    assert receipt.incident_state == "ACTIVE"
    assert receipt.incident_urn is not None
    assert receipt.incident_urn.startswith("urn:li:incident:tripwire-")
    # Every entity Tripwire actually evaluated is attached to the incident.
    assert MODEL.urn in incidents[0].entities


def test_available_remediation_does_not_resolve_a_still_unsafe_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fix Tripwire *found* is not a fix anyone *applied*.

    The submitted change is still unsafe, so the incident must stay ACTIVE. Closing it
    because a patch exists would be the exact over-claim this project exists to prevent.
    """

    from tripwire.domain import RemediationStatus, VerifiedRemediation

    passport = _proposal_passport()
    fixed = passport.model_copy(
        update={
            "remediation": VerifiedRemediation(
                remediation_id="fix_" + "a" * 16,
                status=RemediationStatus.VERIFIED,
                summary="Restored baseline behavior.",
                change_fact_ids=("fact-1",),
                patch="--- candidate.sql\n+++ fixed.sql\n",
                fixed_output_hash="b" * 64,
                restored_evaluations=("model-1",),
            )
        }
    )
    approved = _approved(passport)
    _, graph = _install_fakes(
        monkeypatch, tuple(ref.urn for ref in approved.affected_entities)
    )
    receipt = DataHubMemoryStore(TripwireSettings()).publish(
        passport=fixed, protection=approved
    )

    incidents = graph.aspects("IncidentInfoClass")
    assert incidents[0].status.state == "ACTIVE"
    assert receipt.incident_state == "ACTIVE"
    assert "has not been applied" in incidents[0].status.message
    assert "fix_" in incidents[0].status.message


def test_one_incident_per_asset_so_a_later_safe_run_can_close_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Executed evidence opens the incident, and only executed evidence closes it."""

    approved = _approved(_proposal_passport())
    urns = tuple(ref.urn for ref in approved.affected_entities)

    context = ContextSnapshot(
        root=ROOT,
        facts=(),
        paths=(LineagePath(nodes=(ROOT, MODEL)),),
        coverage=ContextCoverage(
            status=CoverageStatus.COMPLETE,
            required_operations=("get_entities", "get_lineage", "list_schema_fields"),
            completed_operations=("get_entities", "get_lineage", "list_schema_fields"),
            critical_consumers=(MODEL,),
        ),
        provider="recorded-test-context",
        protections=(approved,),
    )
    service = AssessmentService(root=Path.cwd(), demo_dir=Path("demo/fraud"))
    unsafe = service.assess(
        candidate="unsafe_semantic", context=context, resolved_entity=ROOT
    )
    safe = service.assess(
        candidate="safe_additive", context=context, resolved_entity=ROOT
    )

    _, graph = _install_fakes(monkeypatch, urns)
    store = DataHubMemoryStore(TripwireSettings())
    opened = store.publish(passport=unsafe, protection=approved)
    cleared = store.publish(passport=safe, protection=approved)

    # Same asset -> same incident URN, so the second run genuinely closes the first.
    assert opened.incident_urn == cleared.incident_urn
    assert opened.incident_state == "ACTIVE"
    assert cleared.incident_state == "RESOLVED"
    states = [a.status.state for a in graph.aspects("IncidentInfoClass")]
    assert states == ["ACTIVE", "RESOLVED"]


def _passport_with_protection_applied(active):
    """Re-assess a later change with the protection in context, so it actually runs."""

    context = ContextSnapshot(
        root=ROOT,
        facts=(),
        paths=(LineagePath(nodes=(ROOT, MODEL)),),
        coverage=ContextCoverage(
            status=CoverageStatus.COMPLETE,
            required_operations=("get_entities", "get_lineage", "list_schema_fields"),
            completed_operations=("get_entities", "get_lineage", "list_schema_fields"),
            critical_consumers=(MODEL,),
        ),
        provider="recorded-test-context",
        protections=(active,),
    )
    return AssessmentService(root=Path.cwd(), demo_dir=Path("demo/fraud")).assess(
        candidate="unsafe_related",
        context=context,
        resolved_entity=ROOT,
    )


def test_later_run_records_the_protections_real_evaluation_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Once a protection is live, its assertion history reflects each executed run."""

    approved = _approved(_proposal_passport())
    later = _passport_with_protection_applied(approved)
    _, graph = _install_fakes(
        monkeypatch, tuple(ref.urn for ref in approved.affected_entities)
    )
    receipt = DataHubMemoryStore(TripwireSettings()).publish(
        passport=later, protection=approved
    )

    runs = graph.aspects("AssertionRunEventClass")
    assert runs[0].runId == later.run.run_id
    assert runs[0].result.type == "FAILURE"
    assert receipt.assertion_result == "FAILURE"
    # The result carries the executed evidence, not a restatement of the rule.
    assert runs[0].result.nativeResults["tripwire.transaction_id"] == "TX-009"
    assert "tripwire.evaluation_summary" in runs[0].result.nativeResults
    # resolved_entity is present here, so the incident names the changed asset too.
    assert ROOT.urn in graph.aspects("IncidentInfoClass")[0].entities


def test_unverified_verdict_claims_nothing_in_datahub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UNVERIFIED means Tripwire could not prove anything - so it asserts nothing.

    It must neither open an incident (implying a proven failure) nor close one
    (implying a proven pass).
    """

    approved = _approved(_proposal_passport())
    incomplete = ContextSnapshot(
        root=ROOT,
        facts=(),
        paths=(),
        coverage=ContextCoverage(
            status=CoverageStatus.INCOMPLETE,
            required_operations=("get_entities", "get_lineage", "list_schema_fields"),
            completed_operations=("get_entities", "list_schema_fields"),
        ),
        provider="recorded-test-context",
    )
    unverified = AssessmentService(root=Path.cwd(), demo_dir=Path("demo/fraud")).assess(
        candidate="safe_additive", context=incomplete, resolved_entity=ROOT
    )
    assert unverified.verdict.value == "UNVERIFIED"

    _, graph = _install_fakes(
        monkeypatch, tuple(ref.urn for ref in approved.affected_entities)
    )
    with pytest.raises(ValueError, match="UNVERIFIED assessments cannot be published"):
        DataHubMemoryStore(TripwireSettings()).publish(
            passport=unverified, protection=approved
        )

    assert graph.aspects("IncidentInfoClass") == []
    assert graph.aspects("AssertionInfoClass") == []
    assert graph.aspects("AssertionRunEventClass") == []


def test_unapproved_protection_cannot_become_an_assertion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    passport = _proposal_passport()
    proposed = passport.proposed_protection
    assert proposed is not None
    _install_fakes(monkeypatch, tuple(ref.urn for ref in proposed.affected_entities))

    with pytest.raises(ValueError, match="approved protections"):
        DataHubMemoryStore(TripwireSettings()).publish_protection_assertion(proposed)


def test_failed_native_emit_never_reports_a_successful_writeback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing evidence is never success - that rule applies to Tripwire's own writes."""

    passport = _proposal_passport()
    approved = _approved(passport)
    _install_fakes(
        monkeypatch,
        tuple(ref.urn for ref in approved.affected_entities),
        fail_emit=True,
    )

    with pytest.raises(RuntimeError, match="GMS unreachable"):
        DataHubMemoryStore(TripwireSettings()).publish(
            passport=passport, protection=approved
        )
