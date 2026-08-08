"""Idempotent seed of the real Tripwire fraud graph into DataHub."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata import schema_classes as models
from datahub.metadata.urns import (
    CorpUserUrn,
    DomainUrn,
    MlFeatureTableUrn,
    MlFeatureUrn,
    MlModelDeploymentUrn,
)
from datahub.sdk.dataflow import DataFlow
from datahub.sdk.datajob import DataJob
from datahub.sdk.dataset import Dataset
from datahub.sdk.main_client import DataHubClient
from datahub.sdk.mlmodel import MLModel
from datahub.sdk.tag import Tag
from pydantic import BaseModel, ConfigDict

from tripwire.change import DbtManifest
from tripwire.config import TripwireSettings
from tripwire.demo import DEFAULT_MODEL_ARTIFACT, load_model_artifact
from tripwire.provenance import sha256_file, sha256_value


class DataHubSeedResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    datahub_url: str
    seed_version: str
    entities: dict[str, str]
    entity_count: int
    manifest_hash: str


class DataHubSeeder:
    SEED_VERSION = "tripwire-fraud-graph/2.0.0"

    def __init__(self, settings: TripwireSettings):
        self.settings = settings
        token = settings.datahub_token.get_secret_value() if settings.datahub_token else None
        self.client = DataHubClient(server=settings.datahub_gms_url, token=token)
        self.emitter = DatahubRestEmitter(settings.datahub_gms_url, token=token)

    def _emit_aspect(self, urn: str, aspect: Any) -> None:
        self.emitter.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))

    def test_connection(self) -> None:
        self.client.test_connection()

    def seed(self, *, demo_dir: Path) -> DataHubSeedResult:
        model_artifact = load_model_artifact()
        model_artifact_hash = sha256_file(DEFAULT_MODEL_ARTIFACT)
        manifest = DbtManifest.load(demo_dir / "target" / "manifest.json")
        dbt_node = manifest.resolve_source_path(
            "models/fct_fraud_features.sql", project_dir=Path(".")
        )
        feature_dataset_urn = dbt_node.physical_dataset_urn()
        owner = CorpUserUrn("fraud-platform")
        tags = {
            "Tripwire": Tag(name="Tripwire", description="Managed by the Tripwire demo seed."),
            "Production": Tag(
                name="Production", description="Participates in a production-critical path."
            ),
            "Critical": Tag(
                name="Critical", description="Requires complete change-safety evaluation."
            ),
            "PII": Tag(name="PII", description="Contains fields treated as sensitive by policy."),
        }
        raw_dataset = Dataset(
            platform="duckdb",
            name="tripwire_fraud.fraud.raw_transactions",
            display_name="Raw Synthetic Transactions",
            description="Public synthetic transactions used by Tripwire's fraud demo.",
            subtype="Seed",
            owners=[owner],
            tags=[tags[name].urn for name in ("Tripwire", "Production", "PII")],
            schema=[
                ("transaction_id", "VARCHAR", "Stable synthetic transaction ID"),
                ("amount_usd", "DOUBLE", "Transaction value in USD"),
                ("is_international", "BOOLEAN"),
                ("merchant_risk", "VARCHAR"),
                ("customer_age_days", "INTEGER"),
                ("device_age_days", "INTEGER", "Nullable age of observed device"),
                ("chargeback_count_30d", "INTEGER"),
                ("is_refunded", "BOOLEAN"),
            ],
            custom_properties={
                "tripwire.seed.version": self.SEED_VERSION,
                "tripwire.criticality": "production",
                "tripwire.data.classification": "synthetic-public",
            },
        )
        feature_dataset = Dataset(
            platform="duckdb",
            name=dbt_node.physical_dataset_name(),
            display_name="Fraud Features",
            description="Production-critical feature table consumed by model and review agent.",
            subtype="dbt Model",
            owners=[owner],
            tags=[tags[name].urn for name in ("Tripwire", "Production", "Critical")],
            upstreams=[str(raw_dataset.urn)],
            schema=[
                ("transaction_id", "VARCHAR", "Stable synthetic transaction ID"),
                ("amount_usd", "DOUBLE"),
                ("is_international", "BOOLEAN"),
                ("merchant_risk", "VARCHAR"),
                ("customer_age_days", "INTEGER"),
                ("device_age_days", "INTEGER"),
                ("chargeback_count_30d", "INTEGER"),
                ("is_refunded", "BOOLEAN"),
                ("fraud_signal", "DOUBLE", "Critical fraud-model input feature"),
            ],
            custom_properties={
                "tripwire.seed.version": self.SEED_VERSION,
                "tripwire.dbt.unique_id": dbt_node.unique_id,
                "tripwire.dbt.original_file_path": dbt_node.original_file_path,
                "tripwire.criticality": "production",
            },
        )

        for tag in tags.values():
            self.client.entities.upsert(tag)

        owner_urn = str(owner)
        self._emit_aspect(
            owner_urn,
            models.CorpUserInfoClass(
                active=True,
                displayName="Fraud Platform Team",
                email="fraud-platform@example.invalid",
                title="Technical Owner",
                system=True,
            ),
        )
        domain_urn = str(DomainUrn("fraud-risk"))
        self._emit_aspect(
            domain_urn,
            models.DomainPropertiesClass(
                name="Fraud & Risk",
                description="Critical fraud detection datasets, models, and agents.",
            ),
        )
        self.client.entities.upsert(raw_dataset)
        self.client.entities.upsert(feature_dataset)
        self._emit_aspect(str(raw_dataset.urn), models.DomainsClass(domains=[domain_urn]))
        self._emit_aspect(str(feature_dataset.urn), models.DomainsClass(domains=[domain_urn]))

        feature_table_urn = str(MlFeatureTableUrn("duckdb", "tripwire_fraud.fraud_features"))
        feature_urn = str(MlFeatureUrn(feature_table_urn, "fraud_signal"))
        self._emit_aspect(
            feature_urn,
            models.MLFeaturePropertiesClass(
                description=f"Fraud signal consumed by {model_artifact.model_version}",
                dataType=models.MLFeatureDataTypeClass.CONTINUOUS,
                sources=[feature_dataset_urn],
                customProperties={"tripwire.seed.version": self.SEED_VERSION},
            ),
        )
        self._emit_aspect(
            feature_table_urn,
            models.MLFeatureTablePropertiesClass(
                description="Versioned feature namespace for the Tripwire fraud demo.",
                mlFeatures=[feature_urn],
                customProperties={
                    "tripwire.seed.version": self.SEED_VERSION,
                    "tripwire.physical.dataset": feature_dataset_urn,
                },
            ),
        )

        agent_flow = DataFlow(
            name="tripwire_fraud_agents",
            platform="tripwire",
            display_name="Tripwire Fraud Agents",
            description="Deterministic fraud consumers registered in DataHub Core.",
            subtype="AI Agent Runtime",
            owners=[owner],
            tags=[tags[name].urn for name in ("Tripwire", "Production", "Critical")],
            custom_properties={"tripwire.seed.version": self.SEED_VERSION},
        )
        agent_job = DataJob(
            name="fraud_review_agent",
            flow=agent_flow,
            display_name="Fraud Review Agent",
            description=(
                "OSS-compatible AI-agent registry representation. Consumes fraud features "
                f"and {model_artifact.model_version} to approve, review, or block transactions."
            ),
            subtype="AI Agent",
            owners=[owner],
            tags=[tags[name].urn for name in ("Tripwire", "Production", "Critical")],
            inlets=[feature_dataset_urn],
            custom_properties={
                "tripwire.entity.kind": "ai_agent",
                "tripwire.agent.version": "fraud-review-agent/1.0.0",
                "tripwire.seed.version": self.SEED_VERSION,
            },
        )
        self.client.entities.upsert(agent_flow)
        self.client.entities.upsert(agent_job)
        self._emit_aspect(str(agent_flow.urn), models.DomainsClass(domains=[domain_urn]))
        self._emit_aspect(str(agent_job.urn), models.DomainsClass(domains=[domain_urn]))

        deployment_urn = str(MlModelDeploymentUrn("tripwire", "fraud_model_prod", "PROD"))
        self._emit_aspect(
            deployment_urn,
            models.MLModelDeploymentPropertiesClass(
                description="Hash-pinned logistic fraud-model deployment.",
                version=models.VersionTagClass(versionTag="2.0.0"),
                status=models.DeploymentStatusClass.IN_SERVICE,
                customProperties={
                    "tripwire.seed.version": self.SEED_VERSION,
                    "tripwire.model.artifact.sha256": model_artifact_hash,
                },
            ),
        )
        model = MLModel(
            id="fraud_logistic_rule",
            platform="tripwire",
            version="2.0.0",
            name="Fraud Risk Calibrator",
            description=(
                "Versioned logistic-regression artifact executed by Tripwire consumer replay."
            ),
            owners=[owner],
            tags=[tags[name].urn for name in ("Tripwire", "Production", "Critical")],
            downstream_jobs=[str(agent_job.urn)],
            custom_properties={
                "tripwire.seed.version": self.SEED_VERSION,
                "tripwire.model.version": model_artifact.model_version,
                "tripwire.model.family": model_artifact.model_family,
                "tripwire.model.artifact.sha256": model_artifact_hash,
                "tripwire.threshold": str(model_artifact.decision_threshold),
            },
        )
        model_props = model._ensure_model_props()
        model_props.mlFeatures = [feature_urn]
        model_props.deployments = [deployment_urn]
        self.client.entities.upsert(model)
        self._emit_aspect(str(model.urn), models.DomainsClass(domains=[domain_urn]))
        # DataHub 1.7 does not register the ``domains`` aspect for
        # ``mlModelDeployment``. The deployment inherits its business context
        # through the domain-scoped model that references it.
        self._emit_aspect(
            str(agent_job.urn),
            models.DataJobInputOutputClass(
                inputDatasets=[feature_dataset_urn],
                outputDatasets=[],
                inputDatajobs=[],
            ),
        )

        entities = {
            "raw_dataset": str(raw_dataset.urn),
            "feature_dataset": feature_dataset_urn,
            "feature_table": feature_table_urn,
            "fraud_feature": feature_urn,
            "fraud_model": str(model.urn),
            "model_deployment": deployment_urn,
            "agent_flow": str(agent_flow.urn),
            "fraud_review_agent": str(agent_job.urn),
            "owner": owner_urn,
            "domain": domain_urn,
        }
        return DataHubSeedResult(
            datahub_url=self.settings.datahub_gms_url,
            seed_version=self.SEED_VERSION,
            entities=entities,
            entity_count=len(entities),
            manifest_hash=sha256_value(
                {"dbt": manifest.metadata, "entities": entities, "version": self.SEED_VERSION}
            ),
        )


def write_seed_result(result: DataHubSeedResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
