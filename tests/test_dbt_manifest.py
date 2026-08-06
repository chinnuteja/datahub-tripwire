import json
from pathlib import Path

import pytest

from tripwire.change import DbtManifest, ManifestResolutionError


def _manifest(path: Path, nodes: dict[str, object]) -> Path:
    path.write_text(json.dumps({"metadata": {"dbt_version": "1.12.0"}, "nodes": nodes}))
    return path


def _node(unique_id: str, original_file_path: str) -> dict[str, object]:
    return {
        "unique_id": unique_id,
        "name": "fct_fraud_features",
        "resource_type": "model",
        "original_file_path": original_file_path,
        "database": "tripwire_fraud",
        "schema": "fraud",
        "alias": "fct_fraud_features",
        "relation_name": '"tripwire_fraud"."fraud"."fct_fraud_features"',
        "compiled_code": "select 1",
        "depends_on": {"nodes": ["seed.tripwire_fraud.raw_transactions"]},
    }


def test_manifest_resolves_windows_and_posix_paths_exactly(tmp_path: Path) -> None:
    path = _manifest(
        tmp_path / "manifest.json",
        {
            "model.tripwire_fraud.fct_fraud_features": _node(
                "model.tripwire_fraud.fct_fraud_features",
                "models\\fct_fraud_features.sql",
            )
        },
    )
    manifest = DbtManifest.load(path)

    resolved = manifest.resolve_source_path(
        "models/fct_fraud_features.sql", project_dir=Path("demo/fraud")
    )

    assert resolved.unique_id == "model.tripwire_fraud.fct_fraud_features"
    assert resolved.physical_dataset_urn() == (
        "urn:li:dataset:(urn:li:dataPlatform:duckdb,tripwire_fraud.fraud.fct_fraud_features,PROD)"
    )


def test_manifest_missing_path_fails_closed(tmp_path: Path) -> None:
    manifest = DbtManifest.load(
        _manifest(
            tmp_path / "manifest.json",
            {"model.tripwire_fraud.fct": _node("model.tripwire_fraud.fct", "models/fct.sql")},
        )
    )

    with pytest.raises(ManifestResolutionError, match="DBT_NODE_NOT_FOUND"):
        manifest.resolve_source_path("models/unknown.sql", project_dir=Path("demo/fraud"))
