# Tripwire

[![Product Quality](https://github.com/chinnuteja/datahub-tripwire/actions/workflows/quality.yml/badge.svg)](https://github.com/chinnuteja/datahub-tripwire/actions/workflows/quality.yml)

> **DataHub maps the organism. Tripwire gives it an immune system.**

Tripwire is an adaptive change-safety agent for data, ML, and AI systems. It uses
DataHub to trace the real consumers of a proposed SQL or dbt change, executes
consumer-specific evaluations against the old and new behavior, produces a concrete
failure witness when behavior breaks, and writes approved protections back so the next
similar change is caught automatically.

**TRACE → TEST → WITNESS → ACT → IMMUNIZE**

## See the proof first

Start with the [two-minute judge walkthrough](docs/JUDGE_WALKTHROUGH.md) for the shortest
path through the hosted proof, public control PRs, and reproducible live run.

Open the [hosted Tripwire evidence console](https://tripwire-datahub.tejachinnu572.chatgpt.site)
to inspect the real `TX-009` witness, move through the five-stage safety path, compare the
first learned failure with the later automatic catch, and download the underlying Change
Passport. The UI is built from the committed evidence artifacts rather than a separate
hard-coded verdict.

For a zero-setup review, compare the commit-bound
[unsafe and safe public-PR proof](examples/public-proof/README.md), inspect the real
[unsafe draft PR and failing Check](https://github.com/chinnuteja/datahub-tripwire/pull/1),
inspect the real [safe PR and successful Check](https://github.com/chinnuteja/datahub-tripwire/pull/2),
and follow the current [live DataHub v2 inheritance proof](examples/live-v2/README.md).
The original [learn → approve → remember → catch proof](examples/learned-loop/README.md)
shows where that durable memory came from.
The [proof-bundle index](examples/README.md) explains every judge-visible artifact.

## The winning vertical slice

```text
dbt/SQL change
  → DataHub MCP context and lineage
  → DuckDB baseline/candidate execution
  → fraud feature and hash-pinned logistic model artifact replay
  → Fraud Review Agent behavior replay
  → evidence-backed GitHub verdict
  → DataHub Change Passport and reusable protection
```

Tripwire returns one of three honest verdicts:

- `UNSAFE` — executed evidence proves a critical behavior changed.
- `SAFE_WITHIN_SCOPE` — every declared critical evaluation passed within a clearly
  reported scope.
- `UNVERIFIED` — missing context or incomplete evaluation prevents a safety claim.

The headline demo includes both an unsafe and a safe change, plus a second related
change that is caught by a protection learned from the first. The live path uses a
real, seeded DataHub graph and genuine MCP reads; offline snapshots are test fixtures,
not substitutes for the judge-facing integration.

The model consumer is an executable, typed logistic-regression artifact—not a mocked
API or an inline risk condition. Its version, coefficient contract, decision threshold,
and SHA-256 identity are recorded with every replay. DataHub stores the same artifact
identity on the model and deployment, connecting graph context to the code that actually
produced the evidence.

## Run the verified vertical slice

### Judge quickstart with live DataHub

Prerequisites: Python 3.11-3.13, `uv`, Docker with Compose, and enough free disk for
DataHub's local containers. The bootstrap is idempotent and seeds only synthetic data.

On Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap-phase1.ps1
```

On Linux, macOS, or WSL:

```bash
bash scripts/bootstrap-phase1.sh
```

Both scripts install the locked environment, start DataHub v1.7.0, compile the exact dbt
manifest, seed the fraud lineage graph, verify the official MCP tools, and trace the
critical downstream consumers. No DataHub token is required for the default local stack.

To run the steps manually, first install the locked development environment:

```powershell
uv sync --extra dev
```

Start and prepare the live stack:

```powershell
uv run datahub docker quickstart --version v1.7.0 --accept-version-default
New-Item -ItemType Directory -Force artifacts/runtime | Out-Null
uv run dbt build --project-dir demo/fraud --profiles-dir demo/fraud
```

Then use the live DataHub graph and official MCP server:

```powershell
uv run tripwire datahub seed
uv run tripwire assess --candidate unsafe_semantic `
  --output artifacts/runtime/change-passport-live-unsafe-semantic.json
```

For a pull request, Tripwire can load the exact SQL at Git's base and head revisions,
parse deterministic SQL AST facts, resolve the changed dbt node through `manifest.json`,
and use the resulting exact DataHub URN for context retrieval:

```powershell
uv run tripwire assess-git `
  --base-ref origin/main `
  --head-ref HEAD `
  --changed-path demo/fraud/models/fct_fraud_features.sql `
  --manifest-path demo/fraud/target/manifest.json `
  --project-dir demo/fraud
```

Formatting and comments produce no semantic facts. Unsupported Jinja, ambiguous model
paths, missing revisions, and context-root mismatches fail closed with exit code `2`.

For development and CI without external services, the commands below use an explicitly
recorded DataHub context. Live DataHub MCP remains the default whenever `--context-file`
is omitted; Tripwire never silently falls back to a recording.

```powershell
# Proves a semantic change alters both a model score and an agent decision.
uv run tripwire assess --candidate unsafe_semantic `
  --context-file examples/contexts/fraud-feature-recorded.json `
  --output artifacts/runtime/change-passport-unsafe-semantic.json

# Proves an additive change is safe within the evaluated scope.
uv run tripwire assess --candidate safe_additive `
  --context-file examples/contexts/fraud-feature-recorded.json `
  --output artifacts/runtime/change-passport-safe-additive.json

# Proves a renamed critical column breaks every executable consumer evaluation.
uv run tripwire assess --candidate unsafe_mechanical `
  --context-file examples/contexts/fraud-feature-recorded.json `
  --output artifacts/runtime/change-passport-unsafe-mechanical.json
```

Tripwire is CI-native: `SAFE_WITHIN_SCOPE` exits `0`, `UNSAFE` exits `1`, and
`UNVERIFIED` exits `2`. Each run writes a machine-readable Change Passport containing
the traced consumers, executed evaluations, verdict, limitations, and—when one exists—a
minimal counterexample plus a proposed reusable protection.

## Publish a real GitHub Check

Tripwire maps its three honest verdicts directly to enforceable GitHub Check conclusions:

| Tripwire verdict | GitHub conclusion | Meaning |
|---|---|---|
| `UNSAFE` | `failure` | Executed critical evidence blocks the change. |
| `SAFE_WITHIN_SCOPE` | `success` | Every declared critical evaluation passed. |
| `UNVERIFIED` | `action_required` | Missing evidence can never appear as safe. |

The checked-in workflow under `.github/workflows/tripwire.yml` runs the evidence engine,
publishes the Check, and preserves the Change Passport. Publishing is idempotent: a retry
updates the Check with the matching Tripwire run ID instead of creating duplicates.
The dedicated `Tripwire / Change Safety` Check is emitted on every pull request: changes
outside the supported dbt model scope receive an explicit not-applicable success, one model
is assessed, and multiple models receive `action_required` instead of being guessed.
For pull requests, the workflow compiles the dbt manifest, requires exactly one changed
dbt SQL model, loads that file from Git's base and head revisions, parses normalized AST
facts, resolves its exact DataHub URN, and executes those two SQL revisions. Zero or
multiple models never enter assessment: zero is explicitly out of scope, while multiple
models fail closed for independent review.

You can also render the exact Check body locally without GitHub credentials:

```powershell
uv run tripwire github render `
  --passport examples/learned-loop/01-unsafe-semantic-passport.json `
  --output artifacts/runtime/tripwire-check.md
```

Inside GitHub Actions, `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, and `GITHUB_SHA` are supplied
by the runner. The equivalent publishing command is:

```powershell
uv run tripwire github publish `
  --passport artifacts/runtime/change-passport-github.json `
  --details-url https://tripwire-datahub.tejachinnu572.chatgpt.site
```

## Prove the adaptive-memory loop

The unsafe semantic run proposes a protection but cannot activate it. A human explicitly
approves it, after which Tripwire writes the source Passport and active Protection into
DataHub and tags every affected asset:

```powershell
uv run tripwire protection approve `
  --passport artifacts/runtime/change-passport-live-unsafe-semantic.json `
  --approved-by urn:li:corpuser:fraud-platform
```

Now assess a different SQL implementation that recreates the same behavioral defect:

```powershell
uv run tripwire assess --candidate unsafe_related `
  --output artifacts/runtime/change-passport-live-learned-catch.json
```

The second run retrieves the active protection through live DataHub MCP lineage, replays
its approved `TX-009` fixture, and returns `UNSAFE` with
`LEARNED_PROTECTION_VIOLATED`. Repeating the approval targets the same stable DataHub URNs,
preserves the first approval provenance, and does not duplicate tags. Inspect the complete
four-artifact proof under [`examples/learned-loop/`](examples/learned-loop/).

## Independently replay the minimized witness

Tripwire simplifies a discovered counterexample only when replaying the complete SQL →
model → agent path preserves the behavioral failure. The committed minimized Passport
records five attempted simplifications, two accepted simplifications, and a replay hash.
Verify that evidence in a separate process:

```powershell
uv run tripwire witness replay `
  --passport examples/minimized-witness-passport.json `
  --baseline-sql demo/fraud/sql/baseline.sql `
  --candidate-sql demo/fraud/sql/unsafe_semantic.sql
```

The stored learned-protection fixture is also executed directly. It is not looked up by
transaction ID in the seed dataset, so the organizational memory remains portable.

Run the quality gate:

```powershell
uv run ruff check .
uv run mypy tripwire
uv run pytest --cov=tripwire --cov-report=term-missing
```

## Reuse as a DataHub Skill

Tripwire includes an Agent Skills-compatible workflow at
[`skills/tripwire-change-safety/`](skills/tripwire-change-safety/SKILL.md). It teaches
another agent to assess exact dbt revisions, interpret bounded verdicts, verify model and
owner evidence, publish a Check, and require explicit human approval before writing
protection memory.

Install it for Codex with the same open skills installer documented by DataHub:

```powershell
npx skills add chinnuteja/datahub-tripwire -a codex
```

The package is validated with the standard Agent Skills validator and delegates execution
to Tripwire's tested CLI; it does not duplicate the safety logic in prompt text.

## Current status

The complete fraud slice is implemented and live-verified: typed evidence contracts,
DuckDB/dbt execution, a hash-pinned logistic model artifact, Fraud Review Agent replay,
exact manifest and URN resolution, real DataHub seeding, official MCP reads, three-state
verdicts, minimized witnesses, verified remediation, owner routing, human approval,
DataHub write-back, and inherited protection replay.

Both public PR paths are proven. The unsafe PR's workflow succeeds while Tripwire's
dedicated Check correctly returns `failure`; the safe PR's workflow and dedicated Check
both return `success`. Repository-wide CI separately enforces Ruff, strict Mypy, 90%+
branch coverage, all tests, package construction, coverage-artifact preservation, and the
judge console's production build, server-render tests, and lint rules.
The current [live v2 bundle](examples/live-v2/README.md) binds the MCP context, model
artifact, DataHub write-back, related catch, and safe control to exact engine commits.

## Honest limitations

- The executable evaluator intentionally supports one exceptional fraud vertical slice;
  it is not yet a general SQL safety engine.
- The hosted console presents committed, live-captured evidence. It does not host a
  permanent DataHub backend or allow arbitrary SQL execution from an anonymous browser.
- The Git/AST path currently supports one changed dbt SQL model in the fraud vertical
  slice. Multiple changed models deliberately stop for review.
- `SAFE_WITHIN_SCOPE` is explicitly bounded by DataHub context coverage and the consumers
  that Tripwire actually executed.

## License

Apache License 2.0. See [LICENSE](LICENSE).
