#!/usr/bin/env bash
set -euo pipefail

workspace="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export UV_CACHE_DIR="$workspace/.uv-cache"
export UV_TOOL_DIR="$workspace/.uv-tools"

cd "$workspace"

docker info >/dev/null
uv sync --extra dev
uv run datahub docker quickstart --version v1.7.0 --accept-version-default
mkdir -p artifacts/runtime
uv run dbt build --project-dir demo/fraud --profiles-dir demo/fraud
uv run tripwire demo build --scenario baseline
uv run tripwire datahub seed
uv run tripwire datahub tools

feature_urn="$(uv run python -c 'import json; print(json.load(open("artifacts/runtime/datahub-seed-manifest.json", encoding="utf-8"))["entities"]["feature_dataset"])')"
uv run tripwire datahub trace --urn "$feature_urn"
