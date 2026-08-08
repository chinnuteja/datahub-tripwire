"""Executable fraud-demo transformation, model, and review agent."""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Sequence
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from tripwire.domain import AgentAction, AgentDecision, FraudModelResult
from tripwire.provenance import sha256_file, sha256_value


class DemoBuild(BaseModel):
    """Manifest proving exactly which inputs produced the demo outputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario: str
    data_hash: str
    sql_hash: str
    model_version: str
    model_artifact_hash: str
    agent_version: str
    row_count: int
    features: tuple[dict[str, Any], ...]
    predictions: tuple[FraudModelResult, ...]
    decisions: tuple[AgentDecision, ...]
    output_hash: str


TRANSACTION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("transaction_id", "VARCHAR PRIMARY KEY"),
    ("amount_usd", "DOUBLE NOT NULL"),
    ("is_international", "BOOLEAN NOT NULL"),
    ("merchant_risk", "VARCHAR NOT NULL"),
    ("customer_age_days", "INTEGER NOT NULL"),
    ("device_age_days", "INTEGER"),
    ("chargeback_count_30d", "INTEGER NOT NULL"),
    ("is_refunded", "BOOLEAN NOT NULL"),
)

DEFAULT_MODEL_ARTIFACT = Path(__file__).with_name("fraud_logistic_v2.json")


class LogisticModelArtifact(BaseModel):
    """Strict, executable contract for the pinned fraud probability model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0.0"]
    model_version: str = Field(min_length=1)
    model_family: Literal["logistic_regression"]
    target: Literal["fraud_probability"]
    feature_order: tuple[str, ...] = Field(min_length=1)
    intercept: float
    coefficients: dict[str, float]
    decision_threshold: float = Field(gt=0, lt=1)
    probability_precision: int = Field(ge=1, le=12)
    provenance: dict[str, str]

    @model_validator(mode="after")
    def feature_contract_is_exact(self) -> LogisticModelArtifact:
        if set(self.feature_order) != set(self.coefficients):
            raise ValueError("feature_order must exactly match coefficient names")
        parameters = (self.intercept, *self.coefficients.values())
        if not all(math.isfinite(value) for value in parameters):
            raise ValueError("model parameters must be finite")
        return self


@lru_cache(maxsize=8)
def load_model_artifact(path: Path = DEFAULT_MODEL_ARTIFACT) -> LogisticModelArtifact:
    """Load and validate a versioned model artifact once per process."""

    return LogisticModelArtifact.model_validate_json(path.read_text(encoding="utf-8"))


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise ValueError(f"expected true or false, received {value!r}")
    return normalized == "true"


def load_transactions(path: Path) -> list[dict[str, Any]]:
    """Load and validate the public synthetic transaction fixture."""

    transactions: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        expected = [name for name, _ in TRANSACTION_COLUMNS]
        if reader.fieldnames != expected:
            raise ValueError(f"transaction columns must be {expected!r}")
        for raw in reader:
            transactions.append(
                {
                    "transaction_id": raw["transaction_id"],
                    "amount_usd": float(raw["amount_usd"]),
                    "is_international": _parse_bool(raw["is_international"]),
                    "merchant_risk": raw["merchant_risk"],
                    "customer_age_days": int(raw["customer_age_days"]),
                    "device_age_days": (
                        int(raw["device_age_days"]) if raw["device_age_days"] else None
                    ),
                    "chargeback_count_30d": int(raw["chargeback_count_30d"]),
                    "is_refunded": _parse_bool(raw["is_refunded"]),
                }
            )
    ids = [row["transaction_id"] for row in transactions]
    if len(ids) != len(set(ids)):
        raise ValueError("transaction fixture contains duplicate transaction IDs")
    return transactions


class DuckDBTransformationRuntime:
    """Isolated in-memory SQL execution against a declared input schema."""

    def execute(
        self,
        *,
        sql_path: Path,
        rows: Sequence[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        sql = sql_path.read_text(encoding="utf-8")
        return self.execute_sql(sql=sql, rows=rows)

    def execute_sql(
        self,
        *,
        sql: str,
        rows: Sequence[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Execute supplied SQL in the same isolated runtime used by file scenarios."""

        connection = duckdb.connect(":memory:")
        try:
            columns = ", ".join(f"{name} {kind}" for name, kind in TRANSACTION_COLUMNS)
            connection.execute(f"CREATE TABLE raw_transactions ({columns})")
            placeholders = ", ".join("?" for _ in TRANSACTION_COLUMNS)
            values = [tuple(row[name] for name, _ in TRANSACTION_COLUMNS) for row in rows]
            connection.executemany(
                f"INSERT INTO raw_transactions VALUES ({placeholders})",
                values,
            )
            result = connection.execute(sql)
            names = [item[0] for item in result.description]
            output = [
                {
                    name: float(value) if isinstance(value, Decimal) else value
                    for name, value in zip(names, row, strict=True)
                }
                for row in result.fetchall()
            ]
            return sorted(output, key=lambda row: str(row["transaction_id"]))
        finally:
            connection.close()


class DeterministicFraudModel:
    """A hash-pinned logistic model whose prediction is exactly reproducible."""

    def __init__(self, artifact_path: Path = DEFAULT_MODEL_ARTIFACT) -> None:
        self.artifact = load_model_artifact(artifact_path)
        self.artifact_hash = sha256_file(artifact_path)
        self.version = self.artifact.model_version
        self.threshold = self.artifact.decision_threshold

    def predict(self, feature_row: dict[str, Any]) -> FraudModelResult:
        values = {
            feature: float(feature_row[feature]) for feature in self.artifact.feature_order
        }
        logit = self.artifact.intercept + sum(
            self.artifact.coefficients[feature] * values[feature]
            for feature in self.artifact.feature_order
        )
        probability = round(
            1.0 / (1.0 + math.exp(-logit)),
            self.artifact.probability_precision,
        )
        fraud_signal = values["fraud_signal"]
        return FraudModelResult(
            transaction_id=str(feature_row["transaction_id"]),
            probability=probability,
            predicted_fraud=probability >= self.threshold,
            model_version=self.version,
            model_artifact_hash=self.artifact_hash,
            threshold=self.threshold,
            feature_values={
                "fraud_signal": fraud_signal,
                "amount_usd": float(feature_row["amount_usd"]),
                "is_international": bool(feature_row["is_international"]),
                "merchant_risk": {"low": 0, "medium": 1, "high": 2}[
                    str(feature_row["merchant_risk"])
                ],
                "device_age_days": feature_row["device_age_days"],
                "chargeback_count_30d": int(feature_row["chargeback_count_30d"]),
            },
        )


class FraudReviewAgent:
    """A deterministic production-style consumer of the fraud model."""

    version = "fraud-review-agent/1.0.0"

    def decide(self, model_result: FraudModelResult) -> AgentDecision:
        if model_result.probability >= 0.85:
            action = AgentAction.BLOCK
            reasons = ("HIGH_CONFIDENCE_FRAUD",)
        elif model_result.predicted_fraud:
            action = AgentAction.REVIEW
            reasons = ("MODEL_THRESHOLD_EXCEEDED",)
        else:
            action = AgentAction.APPROVE
            reasons = ("MODEL_BELOW_REVIEW_THRESHOLD",)
        return AgentDecision(
            transaction_id=model_result.transaction_id,
            action=action,
            reason_codes=reasons,
            agent_version=self.version,
            model_result=model_result,
        )


class FraudReplaySession:
    """Reuse one isolated DuckDB connection while minimizing a witness."""

    def __init__(self, *, sql: str) -> None:
        self.sql = sql
        self.connection = duckdb.connect(":memory:")
        columns = ", ".join(f"{name} {kind}" for name, kind in TRANSACTION_COLUMNS)
        self.connection.execute(f"CREATE TABLE raw_transactions ({columns})")

    def __enter__(self) -> FraudReplaySession:
        return self

    def __exit__(self, *_args: object) -> None:
        self.connection.close()

    def replay(self, transaction: dict[str, Any]) -> AgentDecision:
        self.connection.execute("DELETE FROM raw_transactions")
        placeholders = ", ".join("?" for _ in TRANSACTION_COLUMNS)
        values = tuple(transaction[name] for name, _ in TRANSACTION_COLUMNS)
        self.connection.execute(
            f"INSERT INTO raw_transactions VALUES ({placeholders})",
            values,
        )
        result = self.connection.execute(self.sql)
        names = [item[0] for item in result.description]
        rows = result.fetchall()
        if len(rows) != 1:
            raise ValueError(
                "witness replay requires the transformation to return exactly one row"
            )
        feature = {
            name: float(value) if isinstance(value, Decimal) else value
            for name, value in zip(names, rows[0], strict=True)
        }
        prediction = DeterministicFraudModel().predict(feature)
        return FraudReviewAgent().decide(prediction)


@lru_cache(maxsize=512)
def _replay_fraud_transaction_cached(sql: str, transaction_json: str) -> AgentDecision:
    transaction = json.loads(transaction_json)
    features = DuckDBTransformationRuntime().execute_sql(sql=sql, rows=[transaction])
    if len(features) != 1:
        raise ValueError(
            "witness replay requires the transformation to return exactly one row"
        )
    prediction = DeterministicFraudModel().predict(features[0])
    return FraudReviewAgent().decide(prediction)


def replay_fraud_transaction(*, sql: str, transaction: dict[str, Any]) -> AgentDecision:
    """Replay one portable fixture through SQL, model, and agent in isolation."""

    transaction_json = json.dumps(
        transaction,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return _replay_fraud_transaction_cached(sql, transaction_json)


def build_demo_world(*, demo_dir: Path, scenario: str = "baseline") -> DemoBuild:
    """Execute SQL → model → agent and return a hash-verifiable manifest."""

    sql_path = demo_dir / "sql" / f"{scenario}.sql"
    if not sql_path.is_file():
        raise ValueError(f"unknown fraud demo scenario: {scenario}")

    return build_demo_world_from_sql(
        demo_dir=demo_dir,
        scenario=scenario,
        sql=sql_path.read_text(encoding="utf-8"),
    )


def build_demo_world_from_sql(*, demo_dir: Path, scenario: str, sql: str) -> DemoBuild:
    """Execute a real Git-loaded SQL revision through model and agent consumers."""

    data_path = demo_dir / "seeds" / "raw_transactions.csv"
    transactions = load_transactions(data_path)
    features = DuckDBTransformationRuntime().execute_sql(sql=sql, rows=transactions)
    model = DeterministicFraudModel()
    agent = FraudReviewAgent()
    predictions = tuple(model.predict(row) for row in features)
    decisions = tuple(agent.decide(result) for result in predictions)
    output_material = {
        "features": features,
        "predictions": [item.model_dump(mode="json") for item in predictions],
        "decisions": [item.model_dump(mode="json") for item in decisions],
    }
    return DemoBuild(
        scenario=scenario,
        data_hash=sha256_file(data_path),
        sql_hash=sha256_value(sql),
        model_version=model.version,
        model_artifact_hash=model.artifact_hash,
        agent_version=agent.version,
        row_count=len(features),
        features=tuple(features),
        predictions=predictions,
        decisions=decisions,
        output_hash=sha256_value(output_material),
    )


def write_demo_build(build: DemoBuild, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
