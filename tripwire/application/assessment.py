"""End-to-end change assessment over typed context and executable evidence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tripwire.demo.fraud import (
    DemoBuild,
    build_demo_world,
    build_demo_world_from_sql,
    load_transactions,
    replay_fraud_transaction,
)
from tripwire.domain import (
    ChangeFact,
    ChangePassport,
    ChangeRequest,
    Counterexample,
    CoverageStatus,
    EntityKind,
    EntityRef,
    EvaluationKind,
    EvaluationResult,
    EvaluationStatus,
    Protection,
    ProtectionStatus,
    Verdict,
)
from tripwire.ports import ContextSnapshot, RuntimeUnavailableError
from tripwire.provenance import create_run_identity, sha256_value
from tripwire.witness import minimize_fraud_witness


class AssessmentService:
    """Turn DataHub context and executed old/new behavior into one verdict."""

    policy_version = "tripwire-policy/1.0.0"
    evaluator_version = "fraud-behavior-evaluator/1.0.0"

    def __init__(self, *, root: Path, demo_dir: Path):
        self.root = root
        self.demo_dir = demo_dir

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
            )
            if baseline_sql is not None
            else build_demo_world(demo_dir=self.demo_dir, scenario="baseline")
        )
        candidate_build: DemoBuild | None = None
        candidate_error: Exception | None = None
        try:
            candidate_build = (
                build_demo_world_from_sql(
                    demo_dir=self.demo_dir,
                    scenario=f"git:{candidate_revision or candidate}",
                    sql=candidate_sql,
                )
                if candidate_sql is not None
                else build_demo_world(demo_dir=self.demo_dir, scenario=candidate)
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
            changed_paths=(changed_path or f"demo/fraud/sql/{candidate}.sql",),
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
        protection = self._propose_protection(
            run_id=run.run_id,
            context=context,
            witness=witness,
        )
        limitations = [
            "The Phase 1 evaluator covers the DuckDB fraud vertical slice only.",
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
                observations = {"changed_transaction_ids": changed}
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
                observations = {"changed_transaction_ids": changed}
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
                    )
                    after = replay_fraud_transaction(
                        sql=candidate_sql,
                        transaction=protection.fixture,
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
            str(item["transaction_id"]): item
            for item in load_transactions(self.demo_dir / "seeds" / "raw_transactions.csv")
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


def write_change_passport(passport: ChangePassport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(passport.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
