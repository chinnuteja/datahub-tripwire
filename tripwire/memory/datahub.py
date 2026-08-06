"""Idempotent Change Passport and learned-protection persistence in DataHub."""

from __future__ import annotations

import json
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from datahub.errors import IngestionAttributionWarning, ItemNotFoundError
from datahub.sdk.dataset import Dataset
from datahub.sdk.main_client import DataHubClient
from datahub.sdk.tag import Tag
from pydantic import BaseModel, ConfigDict

from tripwire.config import TripwireSettings
from tripwire.domain import ChangePassport, EntityKind, Protection, ProtectionStatus
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
        token = settings.datahub_token.get_secret_value() if settings.datahub_token else None
        self.client = DataHubClient(server=settings.datahub_gms_url, token=token)

    def _upsert(self, entity: Any) -> None:
        # Retries intentionally target stable URNs. DataHub warns about the expected
        # partial overwrite even though SDK entities merge the aspects we loaded.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IngestionAttributionWarning)
            self.client.entities.upsert(entity)

    @staticmethod
    def _protection_asset_name(protection: Protection) -> str:
        return f"memory.protections.{protection.protection_id}.v{protection.version}"

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

        return DataHubMemoryReceipt(
            passport_urn=str(passport_asset.urn),
            protection_urn=str(protection_asset.urn),
            tag_urn=str(tag.urn),
            attached_entities=tuple(attached),
            protection_id=protection.protection_id,
            protection_version=protection.version,
            payload_hash=payload_hash,
            published_at=datetime.now(UTC),
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
