"""Context graph capability contract."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from tripwire.domain import ContextCoverage, ContextFact, EntityRef, LineagePath, Protection


class ContextSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    root: EntityRef
    facts: tuple[ContextFact, ...]
    paths: tuple[LineagePath, ...]
    coverage: ContextCoverage
    provider: str
    protections: tuple[Protection, ...] = ()


class ContextGraphPort(Protocol):
    async def health(self) -> bool: ...

    async def resolve_exact(self, urn: str) -> EntityRef: ...

    async def trace_critical_consumers(self, root: EntityRef) -> ContextSnapshot: ...
