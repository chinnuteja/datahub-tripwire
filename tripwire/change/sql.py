"""Deterministic Git and SQL AST change analysis."""

from __future__ import annotations

import importlib.metadata
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import cast

import sqlglot
from sqlglot import exp

from tripwire.change.dbt import DbtManifest
from tripwire.domain import (
    ChangeFact,
    ChangeFactKind,
    ChangeOperation,
    EntityKind,
    EntityRef,
)
from tripwire.provenance import sha256_value


class ChangeAnalysisError(ValueError):
    """Raised when Tripwire cannot produce deterministic change facts."""


@dataclass(frozen=True)
class AnalyzedGitChange:
    base_revision: str
    candidate_revision: str
    changed_path: str
    baseline_sql: str
    candidate_sql: str
    resolved_entity: EntityRef
    dbt_unique_id: str
    facts: tuple[ChangeFact, ...]


_REVISION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_REF_PATTERN = re.compile(r"\{\{\s*ref\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}")
_SOURCE_PATTERN = re.compile(
    r"\{\{\s*source\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}"
)


def render_dbt_sql_for_analysis(sql: str) -> str:
    """Resolve deterministic dbt relation macros without executing arbitrary Jinja."""

    rendered = _REF_PATTERN.sub(lambda match: match.group(1), sql)
    rendered = _SOURCE_PATTERN.sub(lambda match: f"{match.group(1)}.{match.group(2)}", rendered)
    if "{{" in rendered or "{%" in rendered or "{#" in rendered:
        raise ChangeAnalysisError("UNSUPPORTED_DBT_JINJA: SQL contains unresolved Jinja")
    return rendered


def _parse_one(sql: str, *, dialect: str) -> exp.Expression:
    try:
        statements = sqlglot.parse(sql, read=dialect)
    except sqlglot.errors.ParseError as exc:
        raise ChangeAnalysisError(f"SQL_PARSE_FAILED: {exc}") from exc
    if len(statements) != 1 or statements[0] is None:
        raise ChangeAnalysisError("SQL_STATEMENT_COUNT: exactly one SQL statement is required")
    return cast(exp.Expression, statements[0])


def _normalized(expression: exp.Expression, *, dialect: str) -> str:
    return expression.sql(dialect=dialect, pretty=False, comments=False, normalize=True)


def _expressions_by_kind(
    root: exp.Expression, *, dialect: str
) -> dict[ChangeFactKind, Counter[str]]:
    grouped: dict[ChangeFactKind, Counter[str]] = {
        kind: Counter() for kind in ChangeFactKind
    }
    for select in root.find_all(exp.Select):
        grouped[ChangeFactKind.PROJECTION].update(
            _normalized(expression, dialect=dialect) for expression in select.expressions
        )
    for where in root.find_all(exp.Where):
        grouped[ChangeFactKind.PREDICATE][_normalized(where.this, dialect=dialect)] += 1
    for join in root.find_all(exp.Join):
        grouped[ChangeFactKind.JOIN][_normalized(join, dialect=dialect)] += 1
    for aggregate_node in (
        *tuple(root.find_all(exp.Group)),
        *tuple(root.find_all(exp.Having)),
    ):
        grouped[ChangeFactKind.AGGREGATION][
            _normalized(aggregate_node, dialect=dialect)
        ] += 1
    for window_node in root.find_all(exp.Window):
        grouped[ChangeFactKind.WINDOW][_normalized(window_node, dialect=dialect)] += 1
    for cast_node in (*tuple(root.find_all(exp.Cast)), *tuple(root.find_all(exp.TryCast))):
        grouped[ChangeFactKind.CAST][_normalized(cast_node, dialect=dialect)] += 1
    for null_node in (
        *tuple(root.find_all(exp.Coalesce)),
        *tuple(root.find_all(exp.Nullif)),
    ):
        grouped[ChangeFactKind.NULL_HANDLING][
            _normalized(cast(exp.Expression, null_node), dialect=dialect)
        ] += 1
    for column_node in root.find_all(exp.Column):
        grouped[ChangeFactKind.COLUMN][_normalized(column_node, dialect=dialect)] += 1
    for table_node in root.find_all(exp.Table):
        grouped[ChangeFactKind.SOURCE][_normalized(table_node, dialect=dialect)] += 1
    return grouped


def _new_fact(
    *,
    kind: ChangeFactKind,
    operation: ChangeOperation,
    before: str | None,
    after: str | None,
    dialect: str,
    parser_version: str,
) -> ChangeFact:
    material = {
        "kind": kind.value,
        "operation": operation.value,
        "before": before,
        "after": after,
        "dialect": dialect,
        "parser": parser_version,
    }
    return ChangeFact(
        fact_id=f"chg_{sha256_value(material)[:16]}",
        kind=kind,
        operation=operation,
        before_expression=before,
        after_expression=after,
        parser_version=parser_version,
        dialect=dialect,
    )


def analyze_sql_change(
    baseline_sql: str,
    candidate_sql: str,
    *,
    dialect: str = "duckdb",
) -> tuple[ChangeFact, ...]:
    """Compare normalized AST components; formatting and comments produce no facts."""

    baseline = _parse_one(render_dbt_sql_for_analysis(baseline_sql), dialect=dialect)
    candidate = _parse_one(render_dbt_sql_for_analysis(candidate_sql), dialect=dialect)
    baseline_normalized = _normalized(baseline, dialect=dialect)
    candidate_normalized = _normalized(candidate, dialect=dialect)
    if baseline_normalized == candidate_normalized:
        return ()

    parser_version = f"sqlglot/{importlib.metadata.version('sqlglot')}"
    before_groups = _expressions_by_kind(baseline, dialect=dialect)
    after_groups = _expressions_by_kind(candidate, dialect=dialect)
    facts: list[ChangeFact] = []
    for kind in ChangeFactKind:
        if kind is ChangeFactKind.OTHER:
            continue
        removed = sorted((before_groups[kind] - after_groups[kind]).elements())
        added = sorted((after_groups[kind] - before_groups[kind]).elements())
        paired = min(len(removed), len(added))
        facts.extend(
            _new_fact(
                kind=kind,
                operation=ChangeOperation.MODIFIED,
                before=removed[index],
                after=added[index],
                dialect=dialect,
                parser_version=parser_version,
            )
            for index in range(paired)
        )
        facts.extend(
            _new_fact(
                kind=kind,
                operation=ChangeOperation.REMOVED,
                before=value,
                after=None,
                dialect=dialect,
                parser_version=parser_version,
            )
            for value in removed[paired:]
        )
        facts.extend(
            _new_fact(
                kind=kind,
                operation=ChangeOperation.ADDED,
                before=None,
                after=value,
                dialect=dialect,
                parser_version=parser_version,
            )
            for value in added[paired:]
        )
    if not facts:
        facts.append(
            _new_fact(
                kind=ChangeFactKind.OTHER,
                operation=ChangeOperation.MODIFIED,
                before=baseline_normalized,
                after=candidate_normalized,
                dialect=dialect,
                parser_version=parser_version,
            )
        )
    return tuple(facts)


def _validate_git_input(revision: str, changed_path: str) -> None:
    if not _REVISION_PATTERN.fullmatch(revision) or revision.startswith("-"):
        raise ChangeAnalysisError(f"INVALID_GIT_REVISION: {revision!r}")
    portable = PurePosixPath(changed_path.replace("\\", "/"))
    if portable.is_absolute() or ".." in portable.parts or ":" in changed_path:
        raise ChangeAnalysisError(f"INVALID_CHANGED_PATH: {changed_path!r}")


def _git_show(root: Path, revision: str, changed_path: str) -> str:
    _validate_git_input(revision, changed_path)
    portable = str(PurePosixPath(changed_path.replace("\\", "/")))
    result = subprocess.run(
        ["git", "show", f"{revision}:{portable}"],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "git show failed"
        raise ChangeAnalysisError(f"GIT_CONTENT_UNAVAILABLE: {message}")
    return result.stdout


def analyze_git_change(
    *,
    root: Path,
    base_revision: str,
    candidate_revision: str,
    changed_path: str,
    manifest_path: Path,
    project_dir: Path,
    platform: str = "duckdb",
    environment: str = "PROD",
    dialect: str = "duckdb",
) -> AnalyzedGitChange:
    """Load a real Git change, parse it, and resolve its exact dbt/DataHub identity."""

    baseline_sql = _git_show(root, base_revision, changed_path)
    candidate_sql = _git_show(root, candidate_revision, changed_path)
    manifest = DbtManifest.load(manifest_path)
    node = manifest.resolve_source_path(changed_path, project_dir=project_dir)
    facts = analyze_sql_change(baseline_sql, candidate_sql, dialect=dialect)
    entity = EntityRef(
        urn=node.physical_dataset_urn(platform=platform, env=environment),
        kind=EntityKind.DATASET,
        display_name=node.alias,
        platform=platform,
        environment=environment,
    )
    return AnalyzedGitChange(
        base_revision=base_revision,
        candidate_revision=candidate_revision,
        changed_path=str(PurePosixPath(changed_path.replace("\\", "/"))),
        baseline_sql=render_dbt_sql_for_analysis(baseline_sql),
        candidate_sql=render_dbt_sql_for_analysis(candidate_sql),
        resolved_entity=entity,
        dbt_unique_id=node.unique_id,
        facts=facts,
    )
