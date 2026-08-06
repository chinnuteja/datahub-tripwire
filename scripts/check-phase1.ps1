[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $workspace '.uv-cache'
$env:UV_TOOL_DIR = Join-Path $workspace '.uv-tools'

Set-Location -LiteralPath $workspace

docker info | Out-Null
Invoke-WebRequest -Uri http://localhost:8080/config -UseBasicParsing -TimeoutSec 15 | Out-Null
& .\.venv\Scripts\python.exe -m pytest --cov=tripwire --cov-report=term-missing -q
& .\.venv\Scripts\python.exe -m ruff check .
& .\.venv\Scripts\python.exe -m mypy tripwire
& .\.venv\Scripts\dbt.exe build --project-dir demo/fraud --profiles-dir demo/fraud
& .\.venv\Scripts\tripwire.exe datahub seed
& .\.venv\Scripts\tripwire.exe datahub seed

$seed = Get-Content -LiteralPath artifacts\runtime\datahub-seed-manifest.json | ConvertFrom-Json
& .\.venv\Scripts\tripwire.exe datahub trace --urn $seed.entities.feature_dataset
