"""Exact dbt manifest resolution; fuzzy entity guessing is forbidden."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ManifestResolutionError(ValueError):
    """Raised when a source path cannot map to exactly one dbt node."""


class DbtNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    unique_id: str
    name: str
    resource_type: str
    original_file_path: str
    database: str
    schema_name: str = Field(alias="schema")
    alias: str
    relation_name: str
    compiled_code: str | None = None
    depends_on_nodes: tuple[str, ...] = ()

    def physical_dataset_name(self) -> str:
        return f"{self.database}.{self.schema_name}.{self.alias}"

    def physical_dataset_urn(self, *, platform: str = "duckdb", env: str = "PROD") -> str:
        name = self.physical_dataset_name()
        return f"urn:li:dataset:(urn:li:dataPlatform:{platform},{name},{env})"


def _portable_path(value: str) -> str:
    return str(PurePosixPath(value.replace("\\", "/"))).lower()


class DbtManifest:
    def __init__(self, *, path: Path, metadata: dict[str, Any], nodes: tuple[DbtNode, ...]):
        self.path = path
        self.metadata = metadata
        self.nodes = nodes

    @classmethod
    def load(cls, path: Path) -> DbtManifest:
        payload = json.loads(path.read_text(encoding="utf-8"))
        nodes = []
        for raw in payload.get("nodes", {}).values():
            if raw.get("resource_type") not in {"model", "seed", "snapshot"}:
                continue
            nodes.append(
                DbtNode(
                    unique_id=raw["unique_id"],
                    name=raw["name"],
                    resource_type=raw["resource_type"],
                    original_file_path=raw["original_file_path"],
                    database=raw["database"],
                    schema=raw["schema"],
                    alias=raw["alias"],
                    relation_name=raw["relation_name"],
                    compiled_code=raw.get("compiled_code"),
                    depends_on_nodes=tuple(raw.get("depends_on", {}).get("nodes", [])),
                )
            )
        return cls(path=path, metadata=payload.get("metadata", {}), nodes=tuple(nodes))

    def resolve_source_path(self, changed_path: str, *, project_dir: Path) -> DbtNode:
        changed = _portable_path(changed_path)
        root = _portable_path(str(project_dir))
        candidates: list[DbtNode] = []
        for node in self.nodes:
            original = _portable_path(node.original_file_path)
            project_relative = _portable_path(f"{root}/{original}")
            if changed in {original, project_relative}:
                candidates.append(node)
        if not candidates:
            raise ManifestResolutionError(
                f"DBT_NODE_NOT_FOUND: {changed_path!r} is absent from {self.path}"
            )
        if len(candidates) > 1:
            ids = ", ".join(node.unique_id for node in candidates)
            raise ManifestResolutionError(f"DBT_NODE_AMBIGUOUS: {changed_path!r} -> {ids}")
        return candidates[0]
