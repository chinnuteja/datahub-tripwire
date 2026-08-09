# Tripwire judge walkthrough

This is the shortest path to verify the submission. Start with the public evidence; run the live stack only if you want to reproduce it.

## 1. Inspect the result without setup

Open the [Tripwire evidence console](https://tripwire-datahub.tejachinnu572.chatgpt.site). Follow the five stages:

1. **Trace** — the changed dbt asset resolves to real DataHub schema, ownership, and downstream lineage.
2. **Test** — the baseline and candidate execute through DuckDB, the hash-pinned fraud model, and the Fraud Review Agent.
3. **Witness** — `TX-009` is the minimized transaction that changes model and agent behavior.
4. **Act** — the unsafe change is blocked and its remediation is accepted only after the same checks pass.
5. **Immunize** — a human-approved Protection is written to DataHub, retrieved later, and catches a different related SQL regression.

The final safe additive control runs through the same graph, model, agent, and protection and returns `SAFE_WITHIN_SCOPE`.

## 2. Verify the public CI controls

- [Unsafe control PR #1](https://github.com/chinnuteja/datahub-tripwire/pull/1): the workflow completes, while the dedicated `Tripwire / Change Safety` Check correctly concludes `failure`.
- [Safe control PR #2](https://github.com/chinnuteja/datahub-tripwire/pull/2): the workflow and dedicated Check conclude `success`.

The two controls prove that Tripwire does not merely render a red demo. It distinguishes a behavioral regression from a bounded safe change.

## 3. Inspect the captured live evidence

Read the [live DataHub v2 bundle](../examples/live-v2/README.md). Its artifacts include:

- source-hashed DataHub MCP facts and seven lineage paths;
- the unsafe Change Passport and compact Check report;
- the active human-approved Protection;
- the DataHub writeback receipt with stable Passport and Protection URNs;
- a distinct related-change catch;
- the safe control Passport;
- the exact ten-entity seed manifest;
- the 12-row model replay and model artifact hash.

The Passports validate against the public schema and bind evidence to exact source and tool versions.

## 4. Reproduce the live vertical slice

Prerequisites: Python 3.11–3.13, `uv`, Docker Desktop with Compose, and sufficient Docker disk space.

On Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap-phase1.ps1
```

On Linux, macOS, or WSL:

```bash
bash scripts/bootstrap-phase1.sh
```

The bootstrap installs the locked environment, starts DataHub OSS 1.7.0, builds the dbt project, seeds the synthetic graph, discovers the official MCP tools, and traces the critical consumers.

Run the unsafe change. Exit code `1` is expected:

```powershell
uv run tripwire assess --candidate unsafe_semantic `
  --output artifacts/runtime/judge-unsafe.json `
  --requested-by judge
```

Approve its proposed protection and write the Passport and Protection to DataHub:

```powershell
uv run tripwire protection approve `
  --passport artifacts/runtime/judge-unsafe.json `
  --approved-by urn:li:corpuser:fraud-platform
```

Run a different regression. Exit code `1` and reason `LEARNED_PROTECTION_VIOLATED` are expected:

```powershell
uv run tripwire assess --candidate unsafe_related `
  --output artifacts/runtime/judge-related-catch.json `
  --requested-by judge
```

Run the safe control. Exit code `0` and verdict `SAFE_WITHIN_SCOPE` are expected:

```powershell
uv run tripwire assess --candidate safe_additive `
  --output artifacts/runtime/judge-safe.json `
  --requested-by judge
```

## 5. Independently replay and test

Replay the minimized witness in a separate process:

```powershell
uv run tripwire witness replay `
  --passport examples/minimized-witness-passport.json `
  --baseline-sql demo/fraud/sql/baseline.sql `
  --candidate-sql demo/fraud/sql/unsafe_semantic.sql
```

Run the enforced Python quality gate:

```powershell
uv run ruff check .
uv run mypy tripwire
uv run pytest --cov=tripwire --cov-branch --cov-fail-under=90
uv build
```

The hosted console has its own enforced production build, rendered-output tests, and ESLint job in GitHub Actions.

## What is deliberately bounded

Tripwire supports one fraud vertical slice exceptionally well. It does not claim universal SQL safety. Ambiguous assets, unsupported changes, incomplete context, or missing executable consumers produce `UNVERIFIED`. `SAFE_WITHIN_SCOPE` means every discovered critical check passed within the recorded DataHub context and stated limitations.
