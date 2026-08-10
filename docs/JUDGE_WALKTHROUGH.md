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

## 6. See the result inside DataHub's own UI

Tripwire's findings do not live in a Tripwire-shaped side channel. They land on the
governance surfaces DataHub already ships, so a platform team sees them where they are
already looking.

After running the unsafe assessment and approving its protection (steps above), open the
changed dataset:

```
http://localhost:9002/dataset/urn:li:dataset:(urn:li:dataPlatform:duckdb,tripwire_fraud.fraud.fct_fraud_features,PROD)
```

- **Validation tab** — the approved protection appears as a native **Assertion**
  (`CUSTOM` / `TRIPWIRE_PROTECTION`) whose logic is the invariant it enforces, with a run
  recorded per Tripwire run ID.
- **Incidents tab** — the blocked change appears as a native **Incident**, `ACTIVE`,
  attached to the changed dataset *and* every critical consumer that failed.

The captured API response backing this is
[`examples/native-governance/`](../examples/native-governance/README.md) — taken from
DataHub's own GraphQL endpoint, the same one the UI calls.

Two details worth checking, because they are where most tools quietly overstate:

- The incident stays **`ACTIVE`** even though Tripwire found *and verified* a repair. Its
  message reads: *"A verified fix is available (`fix_…`) but has not been applied."* A fix
  that exists is not a fix that shipped. Only a later assessment of the same asset that
  comes back safe flips it to `RESOLVED`.
- An **`UNVERIFIED`** verdict writes **no** assertion result and **no** incident. Tripwire
  proved nothing, so it claims nothing.

## 7. Why this is not circular

Tripwire seeds its own demo entities into DataHub via `tripwire datahub seed`, then reads
them back. That is worth stating plainly, because it is the first thing a careful reviewer
should suspect.

The seed is how this repository ships a reproducible graph without shipping someone's
production catalog. It is not what produces the verdict:

- **The seed writes metadata only.** No verdict, no expected result, and no scenario
  outcome is stored in DataHub. Verdicts come from executing SQL through DuckDB, the
  hash-pinned model artifact, and the review agent.
- **The same seeded graph yields different verdicts.** `unsafe_semantic` returns `UNSAFE`
  and `safe_additive` returns `SAFE_WITHIN_SCOPE` against a byte-identical graph. If the
  graph decided the answer, both would agree.
- **The graph is a live input, not decoration.** Tripwire reads back through the official
  `mcp-server-datahub` tools, not through its own seed manifest; the manifest supplies only
  the starting URN. `test_datahub_graph_consumers_compile_the_evaluation_plan` proves the
  point directly: remove the agent from lineage and Tripwire stops evaluating the agent.
- **The result is falsifiable without DataHub at all.** `tripwire witness replay` re-derives
  `TX-009` in a separate process from the two SQL files alone. If the counterexample were
  an artifact of the seeded metadata, that command would not reproduce it.

Point Tripwire at a DataHub instance containing your own lineage and the read path is
unchanged. What is demo-specific is the executable evaluator behind it, which is stated
below.

## 8. Confirm the evaluator is not fraud-specific

A second vertical slice — inventory stockout risk — runs through the same evaluator with
its own input schema, its own pinned model artifact, its own downstream agent, and a
different class of defect. Exit code `1` and witness `SKU-0102` are expected:

```powershell
uv run tripwire assess --slice inventory --candidate unsafe_backorder_cap `
  --context-file examples/contexts/inventory-feature-recorded.json `
  --output artifacts/runtime/judge-inventory.json `
  --requested-by judge
```

The committed result is [`examples/inventory-slice-passport.json`](../examples/inventory-slice-passport.json),
and the side-by-side comparison is in the [proof bundle README](../examples/README.md).
The fraud regression hides risk through NULL handling; the inventory regression hides it
by lowering an aggregation cap. Neither is pattern-matched — both are caught by execution.

## What is deliberately bounded

Tripwire supports one fraud vertical slice exceptionally well. It does not claim universal SQL safety. Ambiguous assets, unsupported changes, incomplete context, or missing executable consumers produce `UNVERIFIED`. `SAFE_WITHIN_SCOPE` means every discovered critical check passed within the recorded DataHub context and stated limitations.
