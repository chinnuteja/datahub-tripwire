import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from tripwire.cli import app
from tripwire.domain import ContextCoverage, CoverageStatus, EntityKind, EntityRef, LineagePath
from tripwire.ports import ContextSnapshot


def _write_context(path: Path) -> None:
    root = EntityRef(
        urn=(
            "urn:li:dataset:(urn:li:dataPlatform:duckdb,"
            "tripwire_fraud.fraud.fct_fraud_features,PROD)"
        ),
        kind=EntityKind.DATASET,
        display_name="fraud features",
    )
    agent = EntityRef(
        urn=(
            "urn:li:dataJob:(urn:li:dataFlow:(tripwire,tripwire_fraud_agents,PROD),"
            "fraud_review_agent)"
        ),
        kind=EntityKind.DATA_JOB,
        display_name="Fraud Review Agent",
    )
    snapshot = ContextSnapshot(
        root=root,
        facts=(),
        paths=(LineagePath(nodes=(root, agent)),),
        coverage=ContextCoverage(
            status=CoverageStatus.COMPLETE,
            required_operations=("get_entities", "get_lineage", "list_schema_fields"),
            completed_operations=("get_entities", "get_lineage", "list_schema_fields"),
            critical_consumers=(agent,),
        ),
        provider="recorded-cli-test-context",
    )
    path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def test_version() -> None:
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"


def test_demo_compare_shows_boundary_case() -> None:
    result = CliRunner().invoke(app, ["demo", "compare", "--candidate", "unsafe_semantic"])

    assert result.exit_code == 0
    assert '"transaction_id": "TX-009"' in result.stdout
    assert '"baseline_action": "review"' in result.stdout
    assert '"candidate_action": "approve"' in result.stdout


def test_assess_writes_unsafe_passport_and_returns_ci_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    context_path = tmp_path / "context.json"
    artifact_dir = tmp_path / "artifacts"
    _write_context(context_path)
    monkeypatch.setenv("TRIPWIRE_ARTIFACT_DIR", str(artifact_dir))

    result = CliRunner().invoke(
        app,
        [
            "assess",
            "--candidate",
            "unsafe_semantic",
            "--context-file",
            str(context_path),
        ],
    )

    assert result.exit_code == 1
    assert '"verdict": "UNSAFE"' in result.stdout
    passport = json.loads(
        (artifact_dir / "change-passport-unsafe_semantic.json").read_text(encoding="utf-8")
    )
    assert passport["counterexample"]["transaction"]["transaction_id"] == "TX-009"


def test_assess_safe_candidate_returns_success(tmp_path: Path, monkeypatch) -> None:
    context_path = tmp_path / "context.json"
    artifact_dir = tmp_path / "artifacts"
    _write_context(context_path)
    monkeypatch.setenv("TRIPWIRE_ARTIFACT_DIR", str(artifact_dir))

    result = CliRunner().invoke(
        app,
        [
            "assess",
            "--candidate",
            "safe_additive",
            "--context-file",
            str(context_path),
        ],
    )

    assert result.exit_code == 0
    assert '"verdict": "SAFE_WITHIN_SCOPE"' in result.stdout


def test_assess_git_uses_real_revisions_and_exact_context_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_demo = Path("demo/fraud").resolve()
    repo = tmp_path / "repo"
    model_dir = repo / "demo" / "fraud" / "models"
    model_dir.mkdir(parents=True)
    model_path = model_dir / "fct_fraud_features.sql"
    model_path.write_text(
        (source_demo / "sql" / "baseline.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
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
    _git(repo, "init")
    _git(repo, "config", "user.email", "tripwire@example.invalid")
    _git(repo, "config", "user.name", "Tripwire Test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    base = _git(repo, "rev-parse", "HEAD")
    model_path.write_text(
        (source_demo / "sql" / "unsafe_semantic.sql").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "candidate")
    head = _git(repo, "rev-parse", "HEAD")
    context_path = tmp_path / "context.json"
    _write_context(context_path)
    artifact_path = tmp_path / "passport.json"
    monkeypatch.chdir(repo)
    monkeypatch.setenv("TRIPWIRE_DEMO_DIR", str(source_demo))

    result = CliRunner().invoke(
        app,
        [
            "assess-git",
            "--base-ref",
            base,
            "--head-ref",
            head,
            "--changed-path",
            "demo/fraud/models/fct_fraud_features.sql",
            "--manifest-path",
            str(manifest_path),
            "--project-dir",
            "demo/fraud",
            "--context-file",
            str(context_path),
            "--output",
            str(artifact_path),
        ],
    )

    assert result.exit_code == 1
    assert '"verdict": "UNSAFE"' in result.stdout
    passport = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert passport["change"]["base_revision"] == base
    assert passport["change"]["candidate_revision"] == head
    assert passport["resolved_entity"]["urn"].endswith(
        "tripwire_fraud.fraud.fct_fraud_features,PROD)"
    )
    assert any(fact["kind"] == "null_handling" for fact in passport["change_facts"])
    assert passport["counterexample"]["transaction"]["transaction_id"] == "TX-009"
