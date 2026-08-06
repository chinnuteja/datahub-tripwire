"""Official DataHub MCP stdio adapter with raw provenance capture."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, ConfigDict

from tripwire.config import TripwireSettings
from tripwire.domain import (
    ContextAuthority,
    ContextCoverage,
    ContextFact,
    CoverageGap,
    CoverageStatus,
    EntityKind,
    EntityRef,
    LineagePath,
    Protection,
    ProtectionStatus,
)
from tripwire.ports import ContextSnapshot
from tripwire.provenance import sha256_value


class MCPCallEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool: str
    arguments: dict[str, Any]
    result: Any
    started_at: datetime
    completed_at: datetime
    result_hash: str


def _payload_from_result(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is None:
        structured = getattr(result, "structured_content", None)
    if structured:
        if isinstance(structured, dict) and set(structured) == {"result"}:
            return structured["result"]
        return structured

    blocks = getattr(result, "content", [])
    texts: list[str] = [
        text for block in blocks if isinstance((text := getattr(block, "text", None)), str)
    ]
    if len(texts) == 1:
        try:
            return json.loads(texts[0])
        except json.JSONDecodeError:
            return texts[0]
    return texts


def _entity_kind(urn: str, raw_type: str | None = None) -> EntityKind:
    entity_type = urn.split(":", 3)[2] if urn.startswith("urn:li:") else ""
    mapping = {
        "dataset": EntityKind.DATASET,
        "dataJob": EntityKind.DATA_JOB,
        "mlFeature": EntityKind.ML_FEATURE,
        "mlFeatureTable": EntityKind.ML_FEATURE,
        "mlModel": EntityKind.ML_MODEL,
        "mlModelDeployment": EntityKind.ML_DEPLOYMENT,
        "aiAgent": EntityKind.AI_AGENT,
        "corpuser": EntityKind.OWNER,
        "corpGroup": EntityKind.OWNER,
        "domain": EntityKind.DOMAIN,
        "tag": EntityKind.TAG,
        "api": EntityKind.API,
        "service": EntityKind.SERVICE,
    }
    if entity_type in mapping:
        return mapping[entity_type]
    normalized = (raw_type or "").upper()
    if normalized == "DATA_JOB":
        return EntityKind.DATA_JOB
    return EntityKind.UNKNOWN


def _find_name(payload: dict[str, Any], urn: str) -> str:
    for key in ("name", "displayName", "title", "qualifiedName"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    properties = payload.get("properties")
    if isinstance(properties, dict):
        for key in ("name", "displayName", "qualifiedName"):
            value = properties.get(key)
            if isinstance(value, str) and value:
                return value
    return urn


def _entity_ref(payload: dict[str, Any]) -> EntityRef:
    urn = str(payload["urn"])
    raw_type = payload.get("type")
    return EntityRef(
        urn=urn,
        kind=_entity_kind(urn, str(raw_type) if raw_type else None),
        display_name=_find_name(payload, urn),
    )


def _custom_properties(payload: dict[str, Any]) -> dict[str, str]:
    properties = payload.get("properties")
    items = properties.get("customProperties", []) if isinstance(properties, dict) else []
    return {
        str(item["key"]): str(item["value"])
        for item in items
        if isinstance(item, dict) and "key" in item and "value" in item
    }


def _active_protection(payload: dict[str, Any]) -> Protection | None:
    properties = _custom_properties(payload)
    if properties.get("tripwire.memory.kind") != "protection":
        return None
    raw = properties.get("tripwire.protection.payload")
    if not raw:
        raise ValueError("Tripwire protection memory is missing its typed payload")
    protection = Protection.model_validate_json(raw)
    return protection if protection.status is ProtectionStatus.ACTIVE else None


class DataHubMCPSession:
    def __init__(self, settings: TripwireSettings, session: ClientSession):
        self.settings = settings
        self.session = session

    async def list_tool_names(self) -> tuple[str, ...]:
        response = await self.session.list_tools()
        return tuple(sorted(tool.name for tool in response.tools))

    async def call(self, tool: str, arguments: dict[str, Any]) -> MCPCallEvidence:
        started = datetime.now(UTC)
        result = await self.session.call_tool(
            tool,
            arguments,
            read_timeout_seconds=timedelta(seconds=self.settings.mcp_timeout_seconds),
        )
        completed = datetime.now(UTC)
        if bool(getattr(result, "isError", False) or getattr(result, "is_error", False)):
            raise RuntimeError(
                f"DataHub MCP tool {tool} returned an error: {_payload_from_result(result)}"
            )
        payload = _payload_from_result(result)
        return MCPCallEvidence(
            tool=tool,
            arguments=arguments,
            result=payload,
            started_at=started,
            completed_at=completed,
            result_hash=sha256_value(payload),
        )


@asynccontextmanager
async def open_datahub_mcp(
    settings: TripwireSettings,
    *,
    server_log: Path | None = None,
) -> AsyncIterator[DataHubMCPSession]:
    env = dict(os.environ)
    env["DATAHUB_GMS_URL"] = settings.datahub_gms_url
    # The MCP server's optional usage telemetry must never delay or outlive a local
    # evidence run, especially in CI and other network-restricted environments.
    env.setdefault("DATAHUB_TELEMETRY_ENABLED", "false")
    env.setdefault("UV_CACHE_DIR", str((Path.cwd() / ".uv-cache").resolve()))
    env.setdefault("UV_TOOL_DIR", str((Path.cwd() / ".uv-tools").resolve()))
    if settings.datahub_token:
        env["DATAHUB_GMS_TOKEN"] = settings.datahub_token.get_secret_value()
    params = StdioServerParameters(
        command=settings.mcp_command,
        args=list(settings.mcp_args),
        env=env,
        cwd=Path.cwd(),
    )
    log_path = server_log or settings.artifact_dir / "datahub-mcp.stderr.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("a" if server_log else "w", encoding="utf-8")
    try:
        async with (
            stdio_client(params, errlog=log_handle) as streams,
            ClientSession(*streams) as session,
        ):
            await session.initialize()
            yield DataHubMCPSession(settings, session)
    finally:
        log_handle.close()


class DataHubMCPProvider:
    """ContextGraphPort implemented only through genuine DataHub MCP calls."""

    REQUIRED_TOOLS = ("get_entities", "get_lineage", "list_schema_fields")

    def __init__(self, settings: TripwireSettings):
        self.settings = settings

    async def health(self) -> bool:
        async with open_datahub_mcp(self.settings) as mcp:
            tools = await mcp.list_tool_names()
            return all(tool in tools for tool in self.REQUIRED_TOOLS)

    async def list_tools(self) -> tuple[str, ...]:
        async with open_datahub_mcp(self.settings) as mcp:
            return await mcp.list_tool_names()

    async def resolve_exact(self, urn: str) -> EntityRef:
        async with open_datahub_mcp(self.settings) as mcp:
            evidence = await mcp.call("get_entities", {"urns": urn})
        if not isinstance(evidence.result, dict) or evidence.result.get("error"):
            raise ValueError(f"ENTITY_NOT_FOUND: {urn}")
        returned = evidence.result.get("urn")
        if returned != urn:
            raise ValueError(f"ENTITY_IDENTITY_MISMATCH: expected {urn}, got {returned}")
        return _entity_ref(evidence.result)

    async def trace_critical_consumers(self, root: EntityRef) -> ContextSnapshot:
        calls: list[MCPCallEvidence] = []
        gaps: list[CoverageGap] = []
        async with open_datahub_mcp(self.settings) as mcp:
            entity_call = await mcp.call("get_entities", {"urns": root.urn})
            calls.append(entity_call)
            if root.kind is EntityKind.DATASET:
                schema_call = await mcp.call(
                    "list_schema_fields", {"urn": root.urn, "limit": 100, "offset": 0}
                )
                calls.append(schema_call)
            lineage_call = await mcp.call(
                "get_lineage",
                {
                    "urn": root.urn,
                    "upstream": False,
                    "max_hops": 3,
                    "max_results": 100,
                    "offset": 0,
                },
            )
            calls.append(lineage_call)

        lineage_payload = lineage_call.result if isinstance(lineage_call.result, dict) else {}
        direction = lineage_payload.get("downstreams", {})
        search_results = direction.get("searchResults", []) if isinstance(direction, dict) else []
        consumers: list[EntityRef] = []
        protections: list[Protection] = []
        for item in search_results if isinstance(search_results, list) else []:
            entity = item.get("entity") if isinstance(item, dict) else None
            if isinstance(entity, dict) and entity.get("urn"):
                consumers.append(_entity_ref(entity))
                try:
                    protection = _active_protection(entity)
                except ValueError as exc:
                    gaps.append(
                        CoverageGap(
                            code="INVALID_PROTECTION_MEMORY",
                            message=str(exc),
                            entity_urn=str(entity["urn"]),
                            operation="get_lineage",
                        )
                    )
                else:
                    if protection and all(
                        known.protection_id != protection.protection_id
                        or known.version != protection.version
                        for known in protections
                    ):
                        protections.append(protection)

        if isinstance(direction, dict) and (
            direction.get("hasMore") or direction.get("truncatedDueToTokenBudget")
        ):
            gaps.append(
                CoverageGap(
                    code="LINEAGE_TRUNCATED",
                    message="DataHub MCP reported an unresolved downstream lineage frontier",
                    entity_urn=root.urn,
                    operation="get_lineage",
                )
            )
        critical = tuple(
            consumer
            for consumer in consumers
            if consumer.kind
            in {
                EntityKind.ML_MODEL,
                EntityKind.ML_DEPLOYMENT,
                EntityKind.AI_AGENT,
                EntityKind.DATA_JOB,
            }
        )
        if not critical:
            gaps.append(
                CoverageGap(
                    code="NO_CRITICAL_CONSUMER_DISCOVERED",
                    message=(
                        "No downstream model, deployment, or AI agent was returned by DataHub MCP"
                    ),
                    entity_urn=root.urn,
                    operation="get_lineage",
                )
            )

        facts = tuple(
            ContextFact(
                fact_type=f"mcp.{call.tool}",
                subject=root,
                value={"result": call.result},
                authority=ContextAuthority.DATAHUB_MCP,
                operation=call.tool,
                retrieved_at=call.completed_at,
                source_hash=call.result_hash,
            )
            for call in calls
        )
        paths = tuple(
            LineagePath(nodes=(root, consumer), truncated=bool(gaps)) for consumer in consumers
        )
        completed = tuple(call.tool for call in calls)
        status = CoverageStatus.COMPLETE if not gaps else CoverageStatus.INCOMPLETE
        coverage = ContextCoverage(
            status=status,
            required_operations=self.REQUIRED_TOOLS,
            completed_operations=completed,
            critical_consumers=critical,
            gaps=tuple(gaps),
        )
        return ContextSnapshot(
            root=root,
            facts=facts,
            paths=paths,
            coverage=coverage,
            provider="datahub-mcp/0.6.0:live",
            protections=tuple(protections),
        )
