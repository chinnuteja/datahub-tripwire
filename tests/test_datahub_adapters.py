import json
from pathlib import Path
from types import SimpleNamespace

from tripwire.config import TripwireSettings
from tripwire.providers.datahub_mcp import _entity_ref, _payload_from_result
from tripwire.providers.datahub_seed import DataHubSeeder


class _FakeEntities:
    def __init__(self) -> None:
        self.urns: list[str] = []

    def upsert(self, entity: object) -> None:
        self.urns.append(str(entity.urn))  # type: ignore[attr-defined]


class _FakeClient:
    def __init__(self) -> None:
        self.entities = _FakeEntities()


class _FakeEmitter:
    def __init__(self) -> None:
        self.items: list[object] = []

    def emit(self, item: object) -> None:
        self.items.append(item)


def _write_manifest(demo_dir: Path) -> None:
    target = demo_dir / "target"
    target.mkdir(parents=True)
    payload = {
        "metadata": {"dbt_version": "1.12.0", "project_name": "tripwire_fraud"},
        "nodes": {
            "model.tripwire_fraud.fct_fraud_features": {
                "unique_id": "model.tripwire_fraud.fct_fraud_features",
                "name": "fct_fraud_features",
                "resource_type": "model",
                "original_file_path": "models/fct_fraud_features.sql",
                "database": "tripwire_fraud",
                "schema": "fraud",
                "alias": "fct_fraud_features",
                "relation_name": '"tripwire_fraud"."fraud"."fct_fraud_features"',
                "compiled_code": "select * from raw_transactions",
                "depends_on": {"nodes": ["seed.tripwire_fraud.raw_transactions"]},
            }
        },
    }
    (target / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def test_official_mcp_result_normalization_preserves_structured_json() -> None:
    structured = SimpleNamespace(structuredContent={"result": {"urn": "urn:li:tag:Tripwire"}})
    text = SimpleNamespace(
        structuredContent=None,
        content=[SimpleNamespace(text='{"urn":"urn:li:tag:Tripwire"}')],
    )

    assert _payload_from_result(structured) == {"urn": "urn:li:tag:Tripwire"}
    assert _payload_from_result(text) == {"urn": "urn:li:tag:Tripwire"}


def test_mcp_entity_identity_is_derived_from_returned_urn() -> None:
    ref = _entity_ref(
        {
            "urn": "urn:li:dataJob:(urn:li:dataFlow:(tripwire,agents,PROD),fraud_review)",
            "type": "DATA_JOB",
            "name": "Fraud Review Agent",
        }
    )

    assert ref.kind.value == "data_job"
    assert ref.display_name == "Fraud Review Agent"


def test_seed_is_content_stable_and_constructs_real_sdk_entities(tmp_path: Path) -> None:
    demo_dir = tmp_path / "fraud"
    _write_manifest(demo_dir)
    seeder = object.__new__(DataHubSeeder)
    seeder.settings = TripwireSettings()
    seeder.client = _FakeClient()  # type: ignore[assignment]
    seeder.emitter = _FakeEmitter()  # type: ignore[assignment]

    first = seeder.seed(demo_dir=demo_dir)
    second = seeder.seed(demo_dir=demo_dir)

    assert first.entities == second.entities
    assert first.manifest_hash == second.manifest_hash
    assert first.entity_count == 10
    assert first.entities["fraud_review_agent"].startswith("urn:li:dataJob:")
    assert first.entities["fraud_model"].startswith("urn:li:mlModel:")
    assert len(seeder.client.entities.urns) == 18  # type: ignore[attr-defined]
    assert len(seeder.emitter.items) > 0  # type: ignore[attr-defined]
