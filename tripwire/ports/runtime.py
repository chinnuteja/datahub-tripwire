"""Execution runtime capability contracts."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from tripwire.domain import AgentDecision, FraudModelResult


class RuntimeUnavailableError(RuntimeError):
    """The evaluator infrastructure is unavailable; safety cannot be determined."""


class TransformationRuntimePort(Protocol):
    def execute(
        self,
        *,
        sql_path: Path,
        rows: Sequence[dict[str, Any]],
    ) -> list[dict[str, Any]]: ...


class ModelRuntimePort(Protocol):
    version: str

    def predict(self, feature_row: dict[str, Any]) -> FraudModelResult: ...


class AgentRuntimePort(Protocol):
    version: str

    def decide(self, model_result: FraudModelResult) -> AgentDecision: ...
