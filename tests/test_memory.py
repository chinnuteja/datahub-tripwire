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
    client = _FakeClient(urns)
    monkeypatch.setattr(
        "tripwire.memory.datahub.DataHubClient",
        lambda **_: client,
    )
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
