from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tripwire.domain import (
    ContextCoverage,
    CoverageGap,
    CoverageStatus,
    EntityKind,
    EntityRef,
    Protection,
    ProtectionStatus,
)


def test_complete_coverage_rejects_critical_gap() -> None:
    with pytest.raises(ValidationError, match="complete context"):
        ContextCoverage(
            status=CoverageStatus.COMPLETE,
            required_operations=("get_entities", "get_lineage"),
            completed_operations=("get_entities", "get_lineage"),
            gaps=(CoverageGap(code="LINEAGE_CAPPED", message="frontier unresolved"),),
        )


def test_active_protection_requires_human_provenance() -> None:
    asset = EntityRef(
        urn="urn:li:dataset:(urn:li:dataPlatform:duckdb,fraud.features,PROD)",
        kind=EntityKind.DATASET,
        display_name="fraud.features",
    )
    with pytest.raises(ValidationError, match="explicit human approval"):
        Protection(
            protection_id="tp_unknown_device",
            name="Unknown devices remain high risk",
            status=ProtectionStatus.ACTIVE,
            source_change_id="change-1",
            affected_entities=(asset,),
            invariant="Unknown device age must not reduce fraud risk",
            fixture={"transaction_id": "TX-009"},
            version=1,
        )

    accepted = Protection(
        protection_id="tp_unknown_device",
        name="Unknown devices remain high risk",
        status=ProtectionStatus.ACTIVE,
        source_change_id="change-1",
        affected_entities=(asset,),
        invariant="Unknown device age must not reduce fraud risk",
        fixture={"transaction_id": "TX-009"},
        version=1,
        approved_by="urn:li:corpuser:fraud-owner",
        approved_at=datetime.now(UTC),
    )
    assert accepted.status is ProtectionStatus.ACTIVE
