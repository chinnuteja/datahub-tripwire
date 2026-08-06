"""Stable hashing and run identity helpers."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
from pathlib import Path
from typing import Any

from tripwire.domain import RunIdentity


def canonical_json(value: Any) -> str:
    """Serialize evidence in a deterministic, portable form."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def current_commit_sha(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )
    sha = result.stdout.strip()
    return sha if result.returncode == 0 and sha else "UNCOMMITTED"


def installed_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def create_run_identity(
    *,
    root: Path,
    inputs: dict[str, Any],
    policy_version: str = "tripwire-policy/1.0.0",
) -> RunIdentity:
    input_hashes = {name: sha256_value(value) for name, value in sorted(inputs.items())}
    commit_sha = current_commit_sha(root)
    material = {
        "commit": commit_sha,
        "inputs": input_hashes,
        "policy": policy_version,
    }
    run_id = f"tw_{sha256_value(material)[:24]}"
    return RunIdentity.now(
        run_id=run_id,
        commit_sha=commit_sha,
        policy_version=policy_version,
        input_hashes=input_hashes,
        tool_versions={
            "tripwire": installed_version("datahub-tripwire"),
            "datahub-sdk": installed_version("acryl-datahub"),
            "duckdb": installed_version("duckdb"),
            "mcp": installed_version("mcp"),
        },
    )
