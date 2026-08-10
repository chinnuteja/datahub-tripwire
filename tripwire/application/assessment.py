"""End-to-end change assessment over typed context and executable evidence."""

from __future__ import annotations

import difflib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tripwire.demo.fraud import (
    FRAUD_SLICE,
    DemoBuild,
    SliceSpec,
    build_demo_world,
    build_demo_world_from_sql,
    load_transactions,
    replay_fraud_transaction,
)
from tripwire.domain import (
    ChangeFact,
    ChangeFactKind,
    ChangePassport,
    ChangeRequest,
    Counterexample,
    CoverageStatus,
    EntityKind,
    EntityRef,
    EvaluationKind,
    EvaluationResult,
    EvaluationStatus,
    OwnerRoute,
    Protection,
    ProtectionStatus,
    ScopeAccounting,
    Verdict,
    VerifiedRemediation,
)
from tripwire.ports import ContextSnapshot, RuntimeUnavailableError
from tripwire.provenance import create_run_identity, sha256_value
from tripwire.witness import minimize_fraud_witness


def _scope_accounting(
    *, context: ContextSnapshot, evaluations: tuple[EvaluationResult, ...]
) -> ScopeAccounting:
    required = set(context.coverage.required_operations)
    completed = required.intersection(context.coverage.completed_operations)
    discovered = {consumer.urn for consumer in context.coverage.critical_consumers}
    evaluated = {
        result.consumer.urn
        for result in evaluations
        if result.critical and result.consumer.urn in discovered
    }
    return ScopeAccounting(
        required_operations=len(required),
        completed_operations=len(completed),
        critical_consumers_discovered=len(discovered),
        critical_consumers_evaluated=len(evaluated),
        unresolved_gaps=len(context.coverage.gaps),
        lineage_frontier_complete=(
            not any(path.truncated for path in context.paths)
            and not any(gap.code == "LINEAGE_TRUNCATED" for gap in context.coverage.gaps)
        ),
    )


def _owner_routes(context: ContextSnapshot) -> tuple[OwnerRoute, ...]:
    relevant = {context.root.urn, *(item.urn for item in context.coverage.critical_consumers)}
    routes: dict[tuple[str, str], OwnerRoute] = {}

    def visit(value: Any, source_urn: str | None = None) -> None:
        if isinstance(value, dict):
            raw_urn = value.get("urn")
            if isinstance(raw_urn, str) and raw_urn in relevant:
                source_urn = raw_urn
            ownership = value.get("ownership")
            if source_urn and isinstance(ownership, dict):
                owners = ownership.get("owners", [])
                for item in owners if isinstance(owners, list) else []:
                    owner = item.get("owner") if isinstance(item, dict) else None
                    if not isinstance(owner, dict):
                        continue
                    owner_urn = owner.get("urn")
                    if not isinstance(owner_urn, str) or not owner_urn.startswith(
                        ("urn:li:corpuser:", "urn:li:corpGroup:")
                    ):
                        continue
                    properties = owner.get("properties")
                    details = properties if isinstance(properties, dict) else {}
                    display_name = details.get("displayName")
                    email = details.get("email")
                    route = OwnerRoute(
                        owner_urn=owner_urn,
                        display_name=(
                            display_name
                            if isinstance(display_name, str) and display_name
                            else owner_urn.rsplit(":", 1)[-1]
                        ),
                        email=email if isinstance(email, str) and email else None,
                        source_entity_urn=source_urn,
                    )
                    routes[(route.owner_urn, route.source_entity_urn)] = route
            for child in value.values():
                visit(child, source_urn)
        elif isinstance(value, list):
            for child in value:
                visit(child, source_urn)

    for fact in context.facts:
        visit(fact.value)
    return tuple(routes[key] for key in sorted(routes))


class AssessmentService:
    """Turn DataHub context and executed old/new behavior into one verdict."""

    policy_version = "tripwire-policy/1.0.0"
    evaluator_version = "fraud-behavior-evaluator/1.0.0"

    def __init__(self, *, root: Path, demo_dir: Path, spec: SliceSpec = FRAUD_SLICE):
        self.root = root
        self.demo_dir = demo_dir
        self.spec = spec

    def assess(
        self,
        *,
        candidate: str,
        context: ContextSnapshot,
        repository: str = "datahub-tripwire",
        base_revision: str = "baseline",
        candidate_revision: str | None = None,
        requested_by: str = "local-user",
        changed_path: str | None = None,
        resolved_entity: EntityRef | None = None,
        change_facts: tuple[ChangeFact, ...] = (),
        baseline_sql: str | None = None,
        candidate_sql: str | None = None,
    ) -> ChangePassport:
        if (baseline_sql is None) != (candidate_sql is None):
            raise ValueError("baseline_sql and candidate_sql must be provided together")
        baseline_source = baseline_sql or (
            self.demo_dir / "sql" / "baseline.sql"
        ).read_text(encoding="utf-8")
        candidate_path = self.demo_dir / "sql" / f"{candidate}.sql"
        candidate_source = (
            candidate_sql
            if candidate_sql is not None
            else (
                candidate_path.read_text(encoding="utf-8")
                if candidate_path.is_file()
                else None
            )
        )
        baseline = (
            build_demo_world_from_sql(
                demo_dir=self.demo_dir,
                scenario=f"git:{base_revision}",
                sql=baseline_sql,
                spec=self.spec,
            )
            if baseline_sql is not None
            else build_demo_world(demo_dir=self.demo_dir, scenario="baseline", spec=self.spec)
        )
        candidate_build: DemoBuild | None = None
        candidate_error: Exception | None = None
        try:
            candidate_build = (
                build_demo_world_from_sql(
                    demo_dir=self.demo_dir,
                    scenario=f"git:{candidate_revision or candidate}",
                    sql=candidate_sql,
                    spec=self.spec,
                )
                if candidate_sql is not None
                else build_demo_world(demo_dir=self.demo_dir, scenario=candidate, spec=self.spec)
            )
        except Exception as exc:  # evidence is captured below, never silently swallowed
            candidate_error = exc

        run = create_run_identity(
            root=self.root,
            policy_version=self.policy_version,
            inputs={
                "baseline_output_hash": baseline.output_hash,
                "candidate": candidate,
                "candidate_output_hash": (
                    candidate_build.output_hash if candidate_build else None
                ),
                "candidate_error": (
                    f"{type(candidate_error).__name__}: {candidate_error}"
                    if candidate_error
                    else None
                ),
                "context": context.model_dump(mode="json"),
                "change_facts": [fact.model_dump(mode="json") for fact in change_facts],
                "resolved_entity": (
                    resolved_entity.model_dump(mode="json") if resolved_entity else None
                ),
            },
        )
        change = ChangeRequest(
            repository=repository,
            base_revision=base_revision,
            candidate_revision=candidate_revision or candidate,
            changed_paths=(changed_path or f"{self.demo_dir.as_posix()}/sql/{candidate}.sql",),
            requested_by=requested_by,
        )

        evaluations = self._evaluate(
            baseline=baseline,
            candidate=candidate_build,
            candidate_error=candidate_error,
            context=context,
            baseline_sql=baseline_source,
            candidate_sql=candidate_source,
        )
        witness = (
            self._find_witness(
                baseline=baseline,
                candidate=candidate_build,
                baseline_sql=baseline_source,
                candidate_sql=candidate_source,
            )
            if candidate_build and candidate_source is not None
            else None
        )
        verdict, reason_codes = self._decide(context=context, evaluations=evaluations)
        remediation = self._verified_remediation(
            baseline=baseline,
            candidate_sql=candidate_source,
            change_facts=change_facts,
            evaluations=evaluations,
            verdict=verdict,
        )
        protection = self._propose_protection(
            run_id=run.run_id,
            context=context,
            witness=witness,
        )
        limitations = [
            f"The Phase 1 evaluator covers the DuckDB {self.spec.name} vertical slice only.",
            "Safety is bounded by the consumers and lineage returned in Context Coverage.",
        ]
        if context.provider != "datahub-mcp/0.6.0:live":
            limitations.append(f"Context provider was {context.provider}, not live DataHub MCP.")

        return ChangePassport(
            run=run,
            change=change,
            resolved_entity=resolved_entity,
            change_facts=change_facts,
            context=context.facts,
            lineage=context.paths,
            coverage=context.coverage,
            evaluations=evaluations,
            counterexample=witness,
            verdict=verdict,
            reason_codes=reason_codes,
            limitations=tuple(limitations),
            applied_protections=context.protections,
            proposed_protection=protection,
            scope_accounting=_scope_accounting(context=context, evaluations=evaluations),
            owner_routes=_owner_routes(context),
            remediation=remediation,
        )

    def _evaluate(
        self,
        *,
        baseline: DemoBuild,
        candidate: DemoBuild | None,
        candidate_error: Exception | None,
        context: ContextSnapshot,
        baseline_sql: str,
        candidate_sql: str | None,
    ) -> tuple[EvaluationResult, ...]:
        started = datetime.now(UTC)
        results: list[EvaluationResult] = []
        baseline_predictions = {item.transaction_id: item for item in baseline.predictions}
        baseline_decisions = {item.transaction_id: item for item in baseline.decisions}
        candidate_predictions = (
            {item.transaction_id: item for item in candidate.predictions} if candidate else {}
        )
        candidate_decisions = (
            {item.transaction_id: item for item in candidate.decisions} if candidate else {}
        )

        for index, consumer in enumerate(context.coverage.critical_consumers, start=1):
            kind = (
                EvaluationKind.MODEL
                if consumer.kind in {EntityKind.ML_MODEL, EntityKind.ML_DEPLOYMENT}
                else EvaluationKind.AGENT
            )
            observations: dict[str, Any]
            if candidate_error:
                unavailable = isinstance(candidate_error, RuntimeUnavailableError)
                status = (
                    EvaluationStatus.ERROR if unavailable else EvaluationStatus.FAILED
                )
                summary = (
                    "Required evaluation runtime was unavailable."
                    if unavailable
                    else "Candidate transformation failed for a critical consumer."
                )
                observations = {
                    "error_type": type(candidate_error).__name__,
                    "error": str(candidate_error),
                    "failure_class": "runtime_unavailable" if unavailable else "candidate_code",
                }
            elif kind is EvaluationKind.MODEL:
                changed = [
                    transaction_id
                    for transaction_id, before in baseline_predictions.items()
                    if candidate_predictions.get(transaction_id) != before
                ]
                status = EvaluationStatus.FAILED if changed else EvaluationStatus.PASSED
                summary = (
                    f"Model behavior changed for {len(changed)} transaction(s)."
                    if changed
                    else "Model behavior is identical for every replayed transaction."
                )
                observations = {
                    "changed_transaction_ids": changed,
                    "replayed_rows": baseline.row_count,
                    "model_version": baseline.model_version,
                    "model_artifact_hash": baseline.model_artifact_hash,
                }
            else:
                changed = [
                    transaction_id
                    for transaction_id, before in baseline_decisions.items()
                    if (
                        (after := candidate_decisions.get(transaction_id)) is None
                        or after.action != before.action
                    )
                ]
                status = EvaluationStatus.FAILED if changed else EvaluationStatus.PASSED
                summary = (
                    f"Agent behavior changed for {len(changed)} transaction(s)."
                    if changed
                    else "Agent decisions are identical for every replayed transaction."
                )
                observations = {
                    "changed_transaction_ids": changed,
                    "replayed_rows": baseline.row_count,
                    "model_version": baseline.model_version,
                    "model_artifact_hash": baseline.model_artifact_hash,
                    "agent_version": baseline.agent_version,
                }
            results.append(
                EvaluationResult(
                    evaluation_id=f"{kind.value}-{index}",
                    kind=kind,
                    consumer=consumer,
                    status=status,
                    critical=True,
                    summary=summary,
                    observations=observations,
                    started_at=started,
                    completed_at=datetime.now(UTC),
                    evaluator_version=self.evaluator_version,
                )
            )

        for index, protection in enumerate(context.protections, start=1):
            transaction_id = str(protection.fixture.get("transaction_id", ""))
            if candidate_error:
                status = EvaluationStatus.ERROR
                summary = "Learned protection could not run because candidate execution failed."
                observations = {
                    "protection_id": protection.protection_id,
                    "error_type": type(candidate_error).__name__,
                    "error": str(candidate_error),
                }
            elif candidate_sql is None:
                status = EvaluationStatus.ERROR
                summary = "Learned protection could not locate candidate SQL for replay."
                observations = {
                    "protection_id": protection.protection_id,
                    "transaction_id": transaction_id,
                }
            else:
                try:
                    before = replay_fraud_transaction(
                        sql=baseline_sql,
                        transaction=protection.fixture,
                        spec=self.spec,
                    )
                    after = replay_fraud_transaction(
                        sql=candidate_sql,
                        transaction=protection.fixture,
                        spec=self.spec,
                    )
                    status = (
                        EvaluationStatus.FAILED
                        if before != after
                        else EvaluationStatus.PASSED
                    )
                    summary = (
                        "Candidate violates a human-approved learned protection."
                        if status is EvaluationStatus.FAILED
                        else "Candidate preserves the human-approved learned protection."
                    )
                    observations = {
                        "protection_id": protection.protection_id,
                        "protection_version": protection.version,
                        "source_change_id": protection.source_change_id,
                        "approved_by": protection.approved_by,
                        "transaction_id": transaction_id,
                        "fixture_hash": sha256_value(protection.fixture),
                        "baseline_action": before.action.value,
                        "candidate_action": after.action.value,
                        "baseline_probability": before.model_result.probability,
                        "candidate_probability": after.model_result.probability,
                    }
                except Exception as exc:
                    status = EvaluationStatus.ERROR
                    summary = "Learned protection fixture failed during isolated replay."
                    observations = {
                        "protection_id": protection.protection_id,
                        "transaction_id": transaction_id,
                        "fixture_hash": sha256_value(protection.fixture),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
            results.append(
                EvaluationResult(
                    evaluation_id=f"protection-{index}",
                    kind=EvaluationKind.PROTECTION,
                    consumer=context.root,
                    status=status,
                    critical=True,
                    summary=summary,
                    observations=observations,
                    started_at=started,
                    completed_at=datetime.now(UTC),
                    evaluator_version="learned-protection-replay/1.0.0",
                )
            )
        return tuple(results)

    def _find_witness(
        self,
        *,
        baseline: DemoBuild,
        candidate: DemoBuild,
        baseline_sql: str,
        candidate_sql: str,
    ) -> Counterexample | None:
        candidate_decisions = {item.transaction_id: item for item in candidate.decisions}
        transactions = {
            str(item[self.spec.key]): item
            for item in load_transactions(
                self.demo_dir / "seeds" / f"{self.spec.table}.csv", self.spec
            )
        }
        ordered_pairs = [
            (before, candidate_decisions.get(before.transaction_id))
            for before in baseline.decisions
        ]
        action_changes = [
            (before, after)
            for before, after in ordered_pairs
            if after is not None and after.action != before.action
        ]
        other_changes = [
            (before, after)
            for before, after in ordered_pairs
            if after is not None and after != before and after.action == before.action
        ]
        for before, after in (*action_changes, *other_changes):
            assert after is not None
            minimized = minimize_fraud_witness(
                transaction=transactions[before.transaction_id],
                baseline_sql=baseline_sql,
                candidate_sql=candidate_sql,
                spec=self.spec,
            )
            material = {
                "transaction": minimized.transaction,
                "baseline": minimized.baseline.model_dump(mode="json"),
                "candidate": minimized.candidate.model_dump(mode="json"),
            }
            return Counterexample(
                witness_id=f"witness-{before.transaction_id.lower()}",
                transaction=material["transaction"],
                baseline=material["baseline"],
                candidate=material["candidate"],
                violated_invariant=(
                    "Replaying the same transaction must preserve the fraud model output "
                    "and Fraud Review Agent action."
                ),
                replay_hash=sha256_value(material),
                minimization_attempts=minimized.attempted_simplifications,
                accepted_simplifications=minimized.accepted_simplifications,
            )
        return None

    @staticmethod
    def _decide(
        *,
        context: ContextSnapshot,
        evaluations: tuple[EvaluationResult, ...],
    ) -> tuple[Verdict, tuple[str, ...]]:
        if any(
            result.kind is EvaluationKind.PROTECTION
            and result.status is EvaluationStatus.FAILED
            for result in evaluations
        ):
            return Verdict.UNSAFE, ("LEARNED_PROTECTION_VIOLATED",)
        if any(
            result.critical and result.status is EvaluationStatus.FAILED
            for result in evaluations
        ):
            if any("error_type" in result.observations for result in evaluations):
                return Verdict.UNSAFE, ("CANDIDATE_EXECUTION_FAILED",)
            return Verdict.UNSAFE, ("CRITICAL_BEHAVIOR_REGRESSION",)
        if not context.coverage.critical_consumers:
            return Verdict.UNVERIFIED, ("NO_CRITICAL_CONSUMER_EVALUATED",)
        if context.coverage.status is not CoverageStatus.COMPLETE:
            return Verdict.UNVERIFIED, ("INCOMPLETE_CONTEXT_COVERAGE",)
        if any(result.status is not EvaluationStatus.PASSED for result in evaluations):
            return Verdict.UNVERIFIED, ("CRITICAL_EVALUATION_INCOMPLETE",)
        return Verdict.SAFE_WITHIN_SCOPE, ("ALL_CRITICAL_EVALUATIONS_PASSED",)

    @staticmethod
    def _propose_protection(
        *,
        run_id: str,
        context: ContextSnapshot,
        witness: Counterexample | None,
    ) -> Protection | None:
        if witness is None:
            return None
        if any(
            protection.status is ProtectionStatus.ACTIVE
            and protection.invariant == witness.violated_invariant
            and protection.fixture == witness.transaction
            for protection in context.protections
        ):
            return None
        return Protection(
            protection_id=f"protection-{witness.witness_id}",
            name="Preserve fraud review behavior for the discovered witness",
            status=ProtectionStatus.PROPOSED,
            source_change_id=run_id,
            affected_entities=(context.root, *context.coverage.critical_consumers),
            invariant=witness.violated_invariant,
            fixture=witness.transaction,
            version=1,
        )

    def _verified_remediation(
        self,
        *,
        baseline: DemoBuild,
        candidate_sql: str | None,
        change_facts: tuple[ChangeFact, ...],
        evaluations: tuple[EvaluationResult, ...],
        verdict: Verdict,
    ) -> VerifiedRemediation | None:
        if verdict is not Verdict.UNSAFE or candidate_sql is None:
            return None
        null_facts = tuple(
            fact
            for fact in change_facts
            if fact.kind is ChangeFactKind.NULL_HANDLING
            and fact.before_expression
            and fact.after_expression
        )
        if not null_facts:
            return None

        fixed_sql = candidate_sql
        applied_fact_ids: list[str] = []
        for fact in null_facts:
            assert fact.before_expression is not None
            assert fact.after_expression is not None
            fixed_sql, replacements = re.subn(
                re.escape(fact.after_expression),
                fact.before_expression,
                fixed_sql,
                flags=re.IGNORECASE,
            )
            if replacements:
                applied_fact_ids.append(fact.fact_id)
        if not applied_fact_ids or fixed_sql == candidate_sql:
            return None

        try:
            fixed = build_demo_world_from_sql(
                demo_dir=self.demo_dir,
                scenario="verified-remediation",
                sql=fixed_sql,
                spec=self.spec,
            )
        except Exception:
            return None
        if fixed.predictions != baseline.predictions or fixed.decisions != baseline.decisions:
            return None

        restored = tuple(
            result.evaluation_id
            for result in evaluations
            if result.critical
            and result.status is EvaluationStatus.FAILED
            and result.kind in {EvaluationKind.MODEL, EvaluationKind.AGENT}
        )
        if not restored:
            return None
        patch = "".join(
            difflib.unified_diff(
                candidate_sql.splitlines(keepends=True),
                fixed_sql.splitlines(keepends=True),
                fromfile="candidate.sql",
                tofile="tripwire-verified-fix.sql",
            )
        )
        material = {"facts": applied_fact_ids, "patch": patch, "output": fixed.output_hash}
        return VerifiedRemediation(
            remediation_id=f"fix_{sha256_value(material)[:16]}",
            summary=(
                "Restore the baseline null-handling semantics; Tripwire replayed the repair "
                "and recovered identical model predictions and agent decisions."
            ),
            change_fact_ids=tuple(applied_fact_ids),
            patch=patch,
            fixed_output_hash=fixed.output_hash,
            restored_evaluations=restored,
        )


def write_change_passport(passport: ChangePassport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(passport.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
