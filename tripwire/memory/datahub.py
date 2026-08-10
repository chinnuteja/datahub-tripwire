"""Idempotent Change Passport and learned-protection persistence in DataHub."""

from __future__ import annotations

import json
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.errors import IngestionAttributionWarning, ItemNotFoundError
from datahub.ingestion.graph.client import DatahubClientConfig, DataHubGraph
from datahub.metadata.schema_classes import (
    AssertionInfoClass,
    AssertionResultClass,
    AssertionResultTypeClass,
    AssertionRunEventClass,
    AssertionRunStatusClass,
    AssertionTypeClass,
    AuditStampClass,
    CustomAssertionInfoClass,
    IncidentInfoClass,
    IncidentStateClass,
    IncidentStatusClass,
    IncidentTypeClass,
)
from datahub.sdk.dataset import Dataset
from datahub.sdk.main_client import DataHubClient
from datahub.sdk.tag import Tag
from pydantic import BaseModel, ConfigDict

from tripwire.config import TripwireSettings
from tripwire.domain import (
    ChangePassport,
    EntityKind,
    EvaluationStatus,
    Protection,
    ProtectionStatus,
    Verdict,
)
from tripwire.provenance import sha256_value


class DataHubMemoryReceipt(BaseModel):
    """Auditable result of an idempotent DataHub memory publication."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    passport_urn: str
    protection_urn: str
    tag_urn: str
    attached_entities: tuple[str, ...]
    protection_id: str
    protection_version: int
    payload_hash: str
    published_at: datetime
    # Native DataHub governance primitives. Tripwire produces evidence for the
    # governance surfaces DataHub already ships; it does not reinvent them.
    assertion_urn: str
    assertion_run_id: str
    assertion_result: str
    incident_urn: str | None = None
    incident_state: str | None = None


def approve_protection(
    passport: ChangePassport,
    *,
    approved_by: str,
    approved_at: datetime | None = None,
) -> Protection:
    """Promote a proposed witness into active memory with human provenance."""

    if not approved_by.startswith("urn:li:corpuser:"):
        raise ValueError("approved_by must be an exact DataHub corpuser URN")
    proposed = passport.proposed_protection
    if proposed is None:
        raise ValueError("the Change Passport does not contain a proposed protection")
    material = proposed.model_dump(mode="python")
    material.update(
        status=ProtectionStatus.ACTIVE,
        approved_by=approved_by,
        approved_at=approved_at or datetime.now(UTC),
    )
    return Protection.model_validate(material)


class DataHubMemoryStore:
    """Write accepted Tripwire memory into first-class, searchable DataHub assets."""

    def __init__(self, settings: TripwireSettings):
        self.settings = settings
        self._token = (
            settings.datahub_token.get_secret_value() if settings.datahub_token else None
        )
        self.client = DataHubClient(server=settings.datahub_gms_url, token=self._token)
        self._graph: DataHubGraph | None = None

    @property
    def graph(self) -> DataHubGraph:
        """Lazily open the raw graph used for aspects the typed SDK does not model.

        Assertions and Incidents have no `datahub.sdk` entity class in OSS, and
        `DataHubClient.assertions` requires the paid `acryl-datahub-cloud` package.
        Emitting MCPs against the graph is the supported open-source path.
        """

        if self._graph is None:
            self._graph = DataHubGraph(
                DatahubClientConfig(server=self.settings.datahub_gms_url, token=self._token)
            )
        return self._graph

    def _emit(self, entity_urn: str, aspect: Any) -> None:
        self.graph.emit_mcp(
            MetadataChangeProposalWrapper(entityUrn=entity_urn, aspect=aspect)
        )

    def _stamp(self, when: datetime, actor: str | None = None) -> AuditStampClass:
        return AuditStampClass(
            time=int(when.timestamp() * 1000),
            actor=actor or "urn:li:corpuser:datahub",
        )

    @staticmethod
    def assertion_urn(protection: Protection) -> str:
        return (
            "urn:li:assertion:"
            f"tripwire-{protection.protection_id}-v{protection.version}"
        )

    @staticmethod
    def incident_urn(passport: ChangePassport) -> str:
        """Key the incident on the changed asset, not the run.

        One asset owns one Tripwire incident across runs, so a later safe assessment
        can genuinely close the incident an earlier unsafe one opened. Keying on the
        run id would strand every incident permanently open.
        """

        asset = (
            passport.resolved_entity.urn
            if passport.resolved_entity is not None
            else passport.change.repository
        )
        return f"urn:li:incident:tripwire-{sha256_value(asset)[:24]}"

    @staticmethod
    def _root_dataset(protection: Protection) -> str:
        return next(
            entity.urn
            for entity in protection.affected_entities
            if entity.kind is EntityKind.DATASET
        )

    def _upsert(self, entity: Any) -> None:
        # Retries intentionally target stable URNs. DataHub warns about the expected
        # partial overwrite even though SDK entities merge the aspects we loaded.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IngestionAttributionWarning)
            self.client.entities.upsert(entity)

    @staticmethod
    def _protection_asset_name(protection: Protection) -> str:
        return f"memory.protections.{protection.protection_id}.v{protection.version}"

    def publish_protection_assertion(self, protection: Protection) -> str:
        """Publish a human-approved protection as a native DataHub Assertion."""

        if protection.approved_at is None or protection.approved_by is None:
            raise ValueError("only approved protections can become assertions")
        urn = self.assertion_urn(protection)
        self._emit(
            urn,
            AssertionInfoClass(
                type=AssertionTypeClass.CUSTOM,
                description=protection.invariant,
                externalUrl=self.settings.datahub_frontend_url,
                customAssertion=CustomAssertionInfoClass(
                    type="TRIPWIRE_PROTECTION",
                    entity=self._root_dataset(protection),
                    logic=protection.invariant,
                ),
                customProperties={
                    "tripwire.protection.id": protection.protection_id,
                    "tripwire.protection.name": protection.name,
                    "tripwire.protection.version": str(protection.version),
                    "tripwire.protection.status": protection.status.value,
                    "tripwire.protection.approved_by": protection.approved_by,
                    "tripwire.protection.approved_at": protection.approved_at.isoformat(),
                    "tripwire.protection.source_change_id": protection.source_change_id,
                    "tripwire.protection.fixture_hash": sha256_value(protection.fixture),
                },
                lastUpdated=self._stamp(protection.approved_at, protection.approved_by),
            ),
        )
        return urn

    def record_assertion_run(
        self,
        *,
        passport: ChangePassport,
        protection: Protection,
    ) -> tuple[str, str]:
        """Record this assessment as a native assertion run, giving it pass/fail history.

        This is what a custom dataset can never provide: the protection shows up in
        DataHub's own Assertions surface with a result per Tripwire run.
        """

        assertion = self.assertion_urn(protection)
        evaluation = next(
            (
                item
                for item in passport.evaluations
                if item.observations.get("protection_id") == protection.protection_id
            ),
            None,
        )
        if evaluation is not None:
            result_type = (
                AssertionResultTypeClass.FAILURE
                if evaluation.status is EvaluationStatus.FAILED
                else AssertionResultTypeClass.SUCCESS
                if evaluation.status is EvaluationStatus.PASSED
                else AssertionResultTypeClass.ERROR
            )
        elif passport.counterexample is not None and str(
            passport.counterexample.transaction.get("transaction_id")
        ) == str(protection.fixture.get("transaction_id")):
            # First publish: the protection did not run in this passport, it was born
            # from it. The witness is precisely the failure that motivated it, so the
            # assertion's first recorded run is that real failure - not a synthetic pass.
            result_type = AssertionResultTypeClass.FAILURE
        else:
            result_type = AssertionResultTypeClass.ERROR
        native: dict[str, str] = {
            "tripwire.run_id": passport.run.run_id,
            "tripwire.verdict": passport.verdict.value,
            "tripwire.candidate": passport.change.candidate_revision,
        }
        if evaluation is not None:
            native["tripwire.evaluation_summary"] = evaluation.summary
            for key in ("transaction_id", "fixture_hash"):
                value = evaluation.observations.get(key)
                if value is not None:
                    native[f"tripwire.{key}"] = str(value)

        self._emit(
            assertion,
            AssertionRunEventClass(
                timestampMillis=int(passport.run.created_at.timestamp() * 1000),
                runId=passport.run.run_id,
                asserteeUrn=self._root_dataset(protection),
                status=AssertionRunStatusClass.COMPLETE,
                assertionUrn=assertion,
                result=AssertionResultClass(type=result_type, nativeResults=native),
            ),
        )
        return assertion, result_type

    def publish_incident(self, passport: ChangePassport) -> tuple[str, str] | None:
        """Open a native Incident for an UNSAFE verdict, or resolve it after a fix.

        Returns None when the verdict warrants no incident, so callers never claim an
        incident that was not actually written.
        """

        if passport.verdict is Verdict.UNVERIFIED:
            return None
        # An available remediation is NOT a resolution: the submitted change is still
        # unsafe until an assessment of the same asset actually comes back safe. Only
        # executed evidence closes the incident.
        state = (
            IncidentStateClass.RESOLVED
            if passport.verdict is Verdict.SAFE_WITHIN_SCOPE
            else IncidentStateClass.ACTIVE
        )
        # The changed asset plus every critical consumer Tripwire actually evaluated.
        urns: list[str] = []
        if passport.resolved_entity is not None:
            urns.append(passport.resolved_entity.urn)
        urns.extend(
            consumer.urn
            for consumer in passport.coverage.critical_consumers
            if consumer.urn not in urns
        )
        if not urns:
            return None
        stamp = self._stamp(passport.run.created_at)
        if state == IncidentStateClass.RESOLVED:
            message = (
                f"Cleared by Tripwire run {passport.run.run_id}: every critical "
                "consumer passed on executed evidence."
            )
            title = "Resolved: executed evidence shows no behavior change"
        else:
            message = f"Opened by Tripwire run {passport.run.run_id}."
            if passport.remediation is not None:
                message += (
                    " A verified fix is available "
                    f"({passport.remediation.remediation_id}) but has not been applied."
                )
            title = "Blocked: executed evidence found a critical behavior change"
        urn = self.incident_urn(passport)
        self._emit(
            urn,
            IncidentInfoClass(
                type=IncidentTypeClass.CUSTOM,
                customType="Tripwire Change Safety",
                entities=urns,
                title=title,
                description="; ".join(passport.reason_codes),
                status=IncidentStatusClass(
                    state=state, lastUpdated=stamp, message=message
                ),
                created=stamp,
            ),
        )
        return urn, state

    def find_active(self, proposed: Protection) -> Protection | None:
        """Return an existing approval so retries preserve human provenance."""

        locator = Dataset(
            platform="tripwire",
            name=self._protection_asset_name(proposed),
        )
        try:
            entity: Any = self.client.entities.get(str(locator.urn))
        except ItemNotFoundError:
            return None
        properties = getattr(entity, "custom_properties", None)
        raw = properties.get("tripwire.protection.payload") if properties else None
        if not raw:
            return None
        active = Protection.model_validate_json(raw)
        if active.status is not ProtectionStatus.ACTIVE:
            return None
        return active

    def publish(
        self,
        *,
        passport: ChangePassport,
        protection: Protection,
    ) -> DataHubMemoryReceipt:
        if protection.status is not ProtectionStatus.ACTIVE:
            raise ValueError("only explicitly approved active protections can be published")

        payload = json.dumps(
            protection.model_dump(mode="json"), separators=(",", ":"), sort_keys=True
        )
        passport_payload = json.dumps(
            passport.model_dump(mode="json"), separators=(",", ":"), sort_keys=True
        )
        payload_hash = sha256_value(protection.model_dump(mode="json"))
        tag = Tag(
            name=f"TripwireProtection_{protection.protection_id}_v{protection.version}",
            display_name=f"Tripwire: {protection.name} (v{protection.version})",
            description=(
                f"Active Tripwire protection approved by {protection.approved_by}; "
                f"source change {protection.source_change_id}."
            ),
        )
        self._upsert(tag)

        root = next(
            entity for entity in protection.affected_entities if entity.kind is EntityKind.DATASET
        )
        passport_asset = Dataset(
            platform="tripwire",
            name=f"memory.passports.{passport.run.run_id}",
            display_name=f"Tripwire Change Passport {passport.run.run_id}",
            description=(
                f"Evidence-backed {passport.verdict.value} decision for "
                f"{passport.change.candidate_revision}."
            ),
            subtype="Tripwire Change Passport",
            upstreams=[root.urn],
            tags=[str(tag.urn)],
            custom_properties={
                "tripwire.memory.kind": "change-passport",
                "tripwire.passport.id": passport.run.run_id,
                "tripwire.passport.verdict": passport.verdict.value,
                "tripwire.passport.payload": passport_payload,
            },
        )
        protection_asset = Dataset(
            platform="tripwire",
            name=self._protection_asset_name(protection),
            display_name=f"Tripwire Protection: {protection.name}",
            description=protection.invariant,
            subtype="Tripwire Protection",
            upstreams=[root.urn],
            tags=[str(tag.urn)],
            custom_properties={
                "tripwire.memory.kind": "protection",
                "tripwire.protection.id": protection.protection_id,
                "tripwire.protection.status": protection.status.value,
                "tripwire.protection.version": str(protection.version),
                "tripwire.protection.payload": payload,
                "tripwire.protection.payload_hash": payload_hash,
            },
        )
        self._upsert(passport_asset)
        self._upsert(protection_asset)

        attached: list[str] = []
        for ref in protection.affected_entities:
            entity: Any = self.client.entities.get(ref.urn)
            add_tag = getattr(entity, "add_tag", None)
            if not callable(add_tag):
                raise TypeError(f"DataHub entity does not support tags: {ref.urn}")
            add_tag(str(tag.urn))
            self._upsert(entity)
            attached.append(ref.urn)

        # Native governance surfaces. These are the writes a DataHub operator actually
        # looks at; the assets above remain the durable evidence blob behind them.
        # Any failure here propagates: a partial write must never be reported as success.
        assertion_urn = self.publish_protection_assertion(protection)
        _, assertion_result = self.record_assertion_run(
            passport=passport, protection=protection
        )
        incident = self.publish_incident(passport)

        return DataHubMemoryReceipt(
            passport_urn=str(passport_asset.urn),
            protection_urn=str(protection_asset.urn),
            tag_urn=str(tag.urn),
            attached_entities=tuple(attached),
            protection_id=protection.protection_id,
            protection_version=protection.version,
            payload_hash=payload_hash,
            published_at=datetime.now(UTC),
            assertion_urn=assertion_urn,
            assertion_run_id=passport.run.run_id,
            assertion_result=assertion_result,
            incident_urn=incident[0] if incident else None,
            incident_state=incident[1] if incident else None,
        )


def write_protection(protection: Protection, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(protection.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_memory_receipt(receipt: DataHubMemoryReceipt, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
