from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tripwire.change import (
    ChangeAnalysisError,
    analyze_git_change,
    analyze_sql_change,
    render_dbt_sql_for_analysis,
)
from tripwire.domain import ChangeFactKind, ChangeOperation

DEMO_SQL = Path("demo/fraud/sql")


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def test_semantic_null_change_is_classified_from_ast() -> None:
    baseline = (DEMO_SQL / "baseline.sql").read_text(encoding="utf-8")
    candidate = (DEMO_SQL / "unsafe_semantic.sql").read_text(encoding="utf-8")

    facts = analyze_sql_change(baseline, candidate)

    null_fact = next(fact for fact in facts if fact.kind is ChangeFactKind.NULL_HANDLING)
    assert null_fact.operation is ChangeOperation.MODIFIED
    assert "COALESCE(device_age_days, 0)" in (null_fact.before_expression or "")
    assert "COALESCE(device_age_days, 365)" in (null_fact.after_expression or "")
    assert any(fact.kind is ChangeFactKind.PROJECTION for fact in facts)


def test_formatting_and_comments_do_not_create_change_facts() -> None:
    baseline = "SELECT transaction_id, amount_usd FROM raw_transactions"
    candidate = "-- explanation\nselect TRANSACTION_ID, amount_usd\nfrom RAW_TRANSACTIONS"

    assert analyze_sql_change(baseline, candidate) == ()


def test_unresolved_jinja_fails_closed() -> None:
    with pytest.raises(ChangeAnalysisError, match="UNSUPPORTED_DBT_JINJA"):
        render_dbt_sql_for_analysis("select * from {{ custom_macro('table') }}")


def test_real_git_revisions_resolve_exact_dbt_and_datahub_identity(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    model_dir = repo / "demo" / "fraud" / "models"
    model_dir.mkdir(parents=True)
    model_path = model_dir / "fct_fraud_features.sql"
    baseline = (
        "select coalesce(device_age_days, 0) as device_age_days "
        "from {{ ref('raw_transactions') }}\n"
    )
    candidate = baseline.replace("device_age_days, 0", "device_age_days, 365")
    model_path.write_text(baseline, encoding="utf-8")
    manifest_path = repo / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "metadata": {"dbt_version": "1.12.0"},
                "nodes": {
                    "model.tripwire_fraud.fct_fraud_features": {
                        "unique_id": "model.tripwire_fraud.fct_fraud_features",
                        "name": "fct_fraud_features",
                        "resource_type": "model",
                        "original_file_path": "models/fct_fraud_features.sql",
                        "database": "tripwire_fraud",
                        "schema": "fraud",
                        "alias": "fct_fraud_features",
                        "relation_name": (
                            '"tripwire_fraud"."fraud"."fct_fraud_features"'
                        ),
                        "compiled_code": "select 1",
                        "depends_on": {"nodes": ["seed.tripwire_fraud.raw_transactions"]},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "tripwire@example.invalid")
    _run_git(repo, "config", "user.name", "Tripwire Test")
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-m", "baseline")
    base = _run_git(repo, "rev-parse", "HEAD")
    model_path.write_text(candidate, encoding="utf-8")
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-m", "candidate")
    head = _run_git(repo, "rev-parse", "HEAD")

    analysis = analyze_git_change(
        root=repo,
        base_revision=base,
        candidate_revision=head,
        changed_path="demo/fraud/models/fct_fraud_features.sql",
        manifest_path=manifest_path,
        project_dir=Path("demo/fraud"),
    )

    assert analysis.dbt_unique_id == "model.tripwire_fraud.fct_fraud_features"
    assert analysis.resolved_entity.urn == (
        "urn:li:dataset:(urn:li:dataPlatform:duckdb,"
        "tripwire_fraud.fraud.fct_fraud_features,PROD)"
    )
    assert analysis.baseline_sql.endswith("from raw_transactions\n")
    assert analysis.candidate_sql.endswith("from raw_transactions\n")
    assert any(fact.kind is ChangeFactKind.NULL_HANDLING for fact in analysis.facts)
