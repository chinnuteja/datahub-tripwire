# Phase 1 Truth Spine Runbook

## Required local services

- Docker Desktop with at least 8 GB of memory available.
- Python 3.11–3.13 and `uv` 0.11 or newer.
- DataHub Core v1.7.0, launched by the bootstrap script.
- Official `mcp-server-datahub` v0.6.0 over stdio.

## One-command bootstrap on Windows

```powershell
.\scripts\bootstrap-phase1.ps1
```

The script refuses to proceed if Docker is unavailable. It then creates the pinned Python
environment, launches DataHub, builds the real dbt project, executes the fraud system,
seeds the graph, starts the official MCP server, and traces from the feature dataset.

## Current-machine Docker recovery

During the first development run on 5 August 2026, Docker Desktop's daemon stopped
responding while the DataHub images were being pulled. Tripwire did not force-kill Docker
because that could interrupt unrelated containers. Close Docker Desktop normally, reopen
it, wait until its engine reports “Running,” and execute the bootstrap command again.
Downloaded image layers and the project-local MCP package cache are reusable.

## Manual proof commands

```powershell
.\.venv\Scripts\dbt.exe build --project-dir demo/fraud --profiles-dir demo/fraud
.\.venv\Scripts\tripwire.exe demo compare --candidate unsafe_semantic
.\.venv\Scripts\tripwire.exe datahub seed
.\.venv\Scripts\tripwire.exe datahub tools
```

Then read the exact feature-dataset URN from
`artifacts/runtime/datahub-seed-manifest.json` and run:

```powershell
.\.venv\Scripts\tripwire.exe datahub trace --urn "<feature_dataset_urn>"
```

## Proof that MCP is genuine

Tripwire launches the locked `mcp-server-datahub==0.6.0` dependency from its active
Python environment using the official MCP Python client. This avoids an implicit package
registry request during every assessment.
Every tool call stores its tool name, arguments, returned payload, timestamps, and SHA-256
hash before normalization. If GMS is unavailable, the MCP process fails explicitly; there
is no automatic snapshot fallback in the live command.

## Agent Registry compatibility

The native Agent Registry interface is currently documented as a DataHub Cloud feature.
For DataHub Core, the seed represents the Fraud Review Agent as a first-class `DataJob`
with subtype `AI Agent`, ownership, domain, criticality tags, input lineage, stable version,
and its model dependency. This is a real searchable graph entity, not an item hard-coded in
Tripwire. A future Cloud adapter can emit native `aiAgent` metadata behind the same domain
contract without changing evaluation logic.

## Gate command

After bootstrap succeeds:

```powershell
.\scripts\check-phase1.ps1
```

It verifies GMS health, strict tests and coverage, lint, typing, dbt execution, two
idempotent seed passes, and a genuine MCP lineage trace.
