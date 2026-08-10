"""Deterministic, executable minimization for the fraud vertical slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tripwire.demo.fraud import FRAUD_SLICE, FraudReplaySession, SliceSpec
from tripwire.domain import AgentDecision


@dataclass(frozen=True)
class MinimizedWitness:
    transaction: dict[str, Any]
    baseline: AgentDecision
    candidate: AgentDecision
    attempted_simplifications: int
    accepted_simplifications: int


def _difference_is_preserved(
    *,
    original_action_change: bool,
    baseline: AgentDecision,
    candidate: AgentDecision,
) -> bool:
    if original_action_change:
        return baseline.action != candidate.action
    return baseline.model_result != candidate.model_result


def minimize_fraud_witness(
    *,
    transaction: dict[str, Any],
    baseline_sql: str,
    candidate_sql: str,
    spec: SliceSpec = FRAUD_SLICE,
) -> MinimizedWitness:
    """Simplify values while repeatedly executing the full downstream behavior."""

    current = dict(transaction)
    with (
        FraudReplaySession(sql=baseline_sql, spec=spec) as baseline_session,
        FraudReplaySession(sql=candidate_sql, spec=spec) as candidate_session,
    ):
        baseline = baseline_session.replay(current)
        candidate = candidate_session.replay(current)
        original_action_change = baseline.action != candidate.action
        if not _difference_is_preserved(
            original_action_change=original_action_change,
            baseline=baseline,
            candidate=candidate,
        ):
            raise ValueError("the supplied transaction is not a behavioral counterexample")

        attempted = 0
        accepted = 0
        for field, values in spec.simplifications:
            for value in values:
                if current.get(field) == value:
                    continue
                attempted += 1
                trial = {**current, field: value}
                trial_baseline = baseline_session.replay(trial)
                trial_candidate = candidate_session.replay(trial)
                if not _difference_is_preserved(
                    original_action_change=original_action_change,
                    baseline=trial_baseline,
                    candidate=trial_candidate,
                ):
                    continue
                current = trial
                baseline = trial_baseline
                candidate = trial_candidate
                accepted += 1
                break

    return MinimizedWitness(
        transaction=current,
        baseline=baseline,
        candidate=candidate,
        attempted_simplifications=attempted,
        accepted_simplifications=accepted,
    )
