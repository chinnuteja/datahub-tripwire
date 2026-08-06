"""Provider-neutral domain objects used by every Tripwire interface."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenModel(BaseModel):
    """Immutable, strictly validated base for evidence-bearing values."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class EntityKind(StrEnum):
    DATASET = "dataset"
    DATA_JOB = "data_job"
    ML_FEATURE = "ml_feature"
    ML_MODEL = "ml_model"
    ML_DEPLOYMENT = "ml_deployment"
    AI_AGENT = "ai_agent"
    OWNER = "owner"
    DOMAIN = "domain"
    TAG = "tag"
    API = "api"
    SERVICE = "service"
    UNKNOWN = "unknown"


class ContextAuthority(StrEnum):
    DATAHUB_MCP = "datahub_mcp"
    DBT_MANIFEST = "dbt_manifest"
    DETERMINISTIC_PARSER = "deterministic_parser"
    EXECUTED_EVALUATOR = "executed_evaluator"
    VERSIONED_POLICY = "versioned_policy"


class CoverageStatus(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    AMBIGUOUS = "ambiguous"
    UNAVAILABLE = "unavailable"


class EvaluationKind(StrEnum):
    DATASET = "dataset"
    FEATURE = "feature"
    MODEL = "model"
    AGENT = "agent"
    GOVERNANCE = "governance"
    PROTECTION = "protection"


class EvaluationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    NOT_RUN = "not_run"


class Verdict(StrEnum):
    UNSAFE = "UNSAFE"
    SAFE_WITHIN_SCOPE = "SAFE_WITHIN_SCOPE"
    UNVERIFIED = "UNVERIFIED"


class ChangeFactKind(StrEnum):
    PROJECTION = "projection"
    PREDICATE = "predicate"
    JOIN = "join"
    AGGREGATION = "aggregation"
    WINDOW = "window"
    CAST = "cast"
    NULL_HANDLING = "null_handling"
    COLUMN = "column"
    SOURCE = "source"
    OTHER = "other"


class ChangeOperation(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class ProtectionStatus(StrEnum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    DISABLED = "disabled"


class AgentAction(StrEnum):
    APPROVE = "approve"
    REVIEW = "review"
    BLOCK = "block"


class EntityRef(FrozenModel):
    urn: str = Field(pattern=r"^urn:li:[^:]+:.+")
    kind: EntityKind
    display_name: str
    platform: str | None = None
    environment: str | None = None


class ContextFact(FrozenModel):
    fact_type: str
    subject: EntityRef
    value: dict[str, Any]
    authority: ContextAuthority
    operation: str
    retrieved_at: datetime
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class LineagePath(FrozenModel):
    nodes: tuple[EntityRef, ...] = Field(min_length=2)
    authority: ContextAuthority = ContextAuthority.DATAHUB_MCP
    operation: str = "get_lineage"
    truncated: bool = False

    @model_validator(mode="after")
    def distinct_endpoints(self) -> LineagePath:
        if self.nodes[0].urn == self.nodes[-1].urn:
            raise ValueError("a lineage path must not have identical endpoints")
        return self


class CoverageGap(FrozenModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    message: str
    entity_urn: str | None = None
    operation: str | None = None
    critical: bool = True


class ContextCoverage(FrozenModel):
    status: CoverageStatus
    required_operations: tuple[str, ...]
    completed_operations: tuple[str, ...]
    critical_consumers: tuple[EntityRef, ...] = ()
    gaps: tuple[CoverageGap, ...] = ()

    @model_validator(mode="after")
    def status_matches_evidence(self) -> ContextCoverage:
        missing = set(self.required_operations) - set(self.completed_operations)
        critical_gaps = [gap for gap in self.gaps if gap.critical]
        if self.status is CoverageStatus.COMPLETE and (missing or critical_gaps):
            raise ValueError("complete context cannot have missing operations or critical gaps")
        if self.status is not CoverageStatus.COMPLETE and not (missing or self.gaps):
            raise ValueError("incomplete context requires a missing operation or explicit gap")
        return self


class ChangeRequest(FrozenModel):
    repository: str
    base_revision: str
    candidate_revision: str
    changed_paths: tuple[str, ...] = Field(min_length=1)
    requested_by: str


class ChangeFact(FrozenModel):
    fact_id: str = Field(pattern=r"^chg_[a-f0-9]{16}$")
    kind: ChangeFactKind
    operation: ChangeOperation
    before_expression: str | None = None
    after_expression: str | None = None
    parser_version: str
    dialect: str

    @model_validator(mode="after")
    def operation_matches_expressions(self) -> ChangeFact:
        if self.operation is ChangeOperation.ADDED and self.after_expression is None:
            raise ValueError("added change facts require an after expression")
        if self.operation is ChangeOperation.REMOVED and self.before_expression is None:
            raise ValueError("removed change facts require a before expression")
        if self.operation is ChangeOperation.MODIFIED and not (
            self.before_expression is not None and self.after_expression is not None
        ):
            raise ValueError("modified change facts require before and after expressions")
        return self


class RunIdentity(FrozenModel):
    run_id: str = Field(pattern=r"^tw_[a-f0-9]{24}$")
    created_at: datetime
    commit_sha: str
    policy_version: str
    input_hashes: dict[str, str]
    tool_versions: dict[str, str]

    @classmethod
    def now(
        cls,
        *,
        run_id: str,
        commit_sha: str,
        policy_version: str,
        input_hashes: dict[str, str],
        tool_versions: dict[str, str],
    ) -> RunIdentity:
        return cls(
            run_id=run_id,
            created_at=datetime.now(UTC),
            commit_sha=commit_sha,
            policy_version=policy_version,
            input_hashes=input_hashes,
            tool_versions=tool_versions,
        )


class FraudModelResult(FrozenModel):
    transaction_id: str
    probability: float = Field(ge=0, le=1)
    predicted_fraud: bool
    model_version: str
    threshold: float = Field(ge=0, le=1)
    feature_values: dict[str, float | int | bool | None]


class AgentDecision(FrozenModel):
    transaction_id: str
    action: AgentAction
    reason_codes: tuple[str, ...] = Field(min_length=1)
    agent_version: str
    model_result: FraudModelResult


class EvaluationResult(FrozenModel):
    evaluation_id: str
    kind: EvaluationKind
    consumer: EntityRef
    status: EvaluationStatus
    critical: bool
    summary: str
    observations: dict[str, Any]
    started_at: datetime
    completed_at: datetime
    evaluator_version: str

    @model_validator(mode="after")
    def valid_duration(self) -> EvaluationResult:
        if self.completed_at < self.started_at:
            raise ValueError("evaluation completion cannot precede its start")
        return self


class EvaluationSpec(FrozenModel):
    evaluation_id: str
    kind: EvaluationKind
    consumer: EntityRef
    critical: bool
    invariant: str
    required_runtime: str
    selected_by_facts: tuple[str, ...] = Field(min_length=1)


class Counterexample(FrozenModel):
    witness_id: str
    transaction: dict[str, Any]
    baseline: dict[str, Any]
    candidate: dict[str, Any]
    violated_invariant: str
    replay_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    minimization_attempts: int = Field(default=0, ge=0)
    accepted_simplifications: int = Field(default=0, ge=0)


class Protection(FrozenModel):
    protection_id: str
    name: str
    status: ProtectionStatus
    source_change_id: str
    affected_entities: tuple[EntityRef, ...] = Field(min_length=1)
    invariant: str
    fixture: dict[str, Any]
    version: int = Field(ge=1)
    approved_by: str | None = None
    approved_at: datetime | None = None

    @model_validator(mode="after")
    def active_requires_approval(self) -> Protection:
        if self.status is ProtectionStatus.ACTIVE and not (self.approved_by and self.approved_at):
            raise ValueError("active protections require explicit human approval provenance")
        return self


class ChangePassport(FrozenModel):
    schema_version: str = "1.0.0"
    run: RunIdentity
    change: ChangeRequest
    resolved_entity: EntityRef | None = None
    change_facts: tuple[ChangeFact, ...] = ()
    context: tuple[ContextFact, ...]
    lineage: tuple[LineagePath, ...]
    coverage: ContextCoverage
    evaluations: tuple[EvaluationResult, ...]
    counterexample: Counterexample | None = None
    verdict: Verdict
    reason_codes: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...]
    applied_protections: tuple[Protection, ...] = ()
    proposed_protection: Protection | None = None

    @model_validator(mode="after")
    def verdict_has_required_evidence(self) -> ChangePassport:
        if self.verdict is Verdict.SAFE_WITHIN_SCOPE:
            if self.coverage.status is not CoverageStatus.COMPLETE:
                raise ValueError("SAFE_WITHIN_SCOPE requires complete context coverage")
            critical = [result for result in self.evaluations if result.critical]
            if not critical or any(
                result.status is not EvaluationStatus.PASSED for result in critical
            ):
                raise ValueError("SAFE_WITHIN_SCOPE requires every critical evaluation to pass")
        if self.verdict is Verdict.UNSAFE:
            failed = any(
                result.critical and result.status is EvaluationStatus.FAILED
                for result in self.evaluations
            )
            governance = "HARD_GOVERNANCE_VIOLATION" in self.reason_codes
            if not (failed or governance):
                raise ValueError(
                    "UNSAFE requires a critical executed failure or hard governance rule"
                )
        return self
