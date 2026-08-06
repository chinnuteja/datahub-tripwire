[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $workspace '.uv-cache'
$env:UV_TOOL_DIR = Join-Path $workspace '.uv-tools'

Set-Location -LiteralPath $workspace

docker info | Out-Null
uv sync --extra dev
& .\.venv\Scripts\datahub.exe docker quickstart --version v1.7.0 --accept-version-default
& .\.venv\Scripts\dbt.exe build --project-dir demo/fraud --profiles-dir demo/fraud
& .\.venv\Scripts\tripwire.exe demo build --scenario baseline
& .\.venv\Scripts\tripwire.exe datahub seed
& .\.venv\Scripts\tripwire.exe datahub tools

$seed = Get-Content -LiteralPath artifacts\runtime\datahub-seed-manifest.json | ConvertFrom-Json
& .\.venv\Scripts\tripwire.exe datahub trace --urn $seed.entities.feature_dataset
