# Tripwire Product Contract

## Product promise

Tripwire prevents a proposed data-code change from silently damaging a downstream
data product, model, or AI agent. It does not infer safety from lineage alone. It uses
DataHub to discover what matters, runs the relevant old-versus-new evaluations, shows
the concrete evidence behind its verdict, and converts approved lessons into durable
organizational protection.

Tripwire is not a metadata chatbot, a generic impact-analysis screen, or an LLM risk
score. DataHub supplies the organizational context graph. Tripwire turns that context
into executable change-safety decisions.

## Memorable operating model

### TRACE

- Parse the proposed SQL or dbt change deterministically.
- Resolve changed dbt nodes through build artifacts and explicit platform mappings;
  never guess an entity identity.
- Read schemas, lineage, ownership, governance signals, ML assets, deployments, and
  registered AI agents through the real DataHub MCP path.
- Report **Context Coverage** and expose missing or capped context.
- Resolve dbt/warehouse siblings and require complete paths to every declared critical
  consumer.

### TEST

- Execute the baseline and candidate transformations against the same versioned input.
- Select evaluations from the types and protections of the affected consumers.
- Compare dataset behavior, fraud features, deterministic model predictions, and the
  Fraud Review Agent's structured decisions.
- Record inputs, code hashes, data hashes, evaluator versions, seeds, and outputs so the
  result is reproducible.

### WITNESS

- When a critical evaluation fails, find and minimize a concrete transaction that
  demonstrates the behavioral difference.
- Display the full causal path: changed expression → changed feature → changed model
  prediction → changed agent action.
- Keep DataHub facts, parsed-change facts, executed observations, and policy decisions
  visibly separated.

### ACT

- Apply deterministic, versioned policy to return exactly one verdict:
  `UNSAFE`, `SAFE_WITHIN_SCOPE`, or `UNVERIFIED`.
- Publish an evidence-rich GitHub Check and a portable Change Passport.
- Block only from executed critical failures or explicit hard governance rules.
- Never describe incomplete evidence as safe.

### IMMUNIZE

- Write an idempotent Change Passport and its disposition back to DataHub.
- Require human approval before a discovered counterexample becomes permanent policy.
- Convert the approved lesson into a versioned regression fixture, contract, assertion,
  or evaluation rule attached to the affected graph assets.
- Retrieve and execute that protection during a later related change.

## Verdict contract

| Verdict | Required evidence | CI behavior |
|---|---|---|
| `UNSAFE` | A critical executed evaluation fails, or a configured hard governance rule is violated | Fail the check and show the witness and owner action |
| `SAFE_WITHIN_SCOPE` | Context coverage is sufficient and every declared critical evaluation passes | Pass while stating the exact evaluated scope and limitations |
| `UNVERIFIED` | Critical context, runtime access, or an evaluation is missing/incomplete | Require evidence or approval; never claim safety |

Confidence is metadata, not a fourth verdict. Low model confidence cannot independently
block a change or turn incomplete evidence into safety.

## Trust architecture

Every Change Passport contains four separately rendered evidence layers:

| Layer | Examples | Authority |
|---|---|---|
| DataHub context | URNs, schemas, lineage paths, owners, tags, models, deployments, AI agents | DataHub MCP |
| Change facts | Changed columns, expressions, predicates, joins, aggregations | Deterministic parser |
| Executed observations | Row/feature diffs, prediction diffs, agent decision diffs, counterexample | Versioned evaluators |
| Policy decision | Verdict, violated rule, required action | Versioned deterministic policy |

The UI, CLI, reports, and GitHub Check must never present inference as a DataHub fact or
an unexecuted hypothesis as an observed failure.

## Headline demonstration world

The demo is a small, deterministic fraud-detection system:

```text
raw transactions
  → dbt/SQL fraud feature transformation
  → fraud feature table
  → deterministic fraud model
  → Fraud Review Agent
  → approve / review / block transaction
```

DataHub contains the corresponding datasets, column lineage, ownership, governance
signals, feature/model/deployment relationships, and AI-agent registration. The demo
does not hard-code the blast radius outside the seeded metadata and explicit criticality
configuration.

### Scenario A — Mechanical interface break

A required feature column is renamed or removed. Tripwire resolves the real consumer
path, executes the candidate, returns `UNSAFE`, and shows the broken reference or
contract as evidence.

### Scenario B — Semantic behavioral regression

A predicate or null-handling change leaves the schema intact but alters a fraud feature.
Tripwire executes both versions, finds a concrete transaction whose model prediction and
agent action change, minimizes that witness, and returns `UNSAFE`.

### Scenario C — Safe additive change

An unused nullable field or documentation-safe change is introduced. All critical
evaluations pass and Tripwire returns `SAFE_WITHIN_SCOPE` with an exact scope statement.

### Scenario D — The graph learned

After a human accepts Scenario B's lesson, Tripwire writes the Change Passport and
protection to DataHub. A distinct but related second change retrieves that learned rule,
runs its executable regression, and is stopped. This proves the write-back is functional
memory, not decorative metadata.

## Non-negotiable judge-facing acceptance criteria

1. A real, seeded DataHub instance contains the complete demo graph.
2. The headline run uses genuine DataHub MCP reads and displays their provenance.
3. The input is a real SQL/dbt diff parsed into deterministic change facts.
4. Changed nodes map to exact DataHub entities without fuzzy guessing.
5. DataHub context leads Tripwire to both a downstream model and a downstream AI agent.
6. Baseline and candidate SQL execute against the same versioned data.
7. The model and the AI agent are replayed and compared.
8. The unsafe scenario produces a concrete, reproducible failing transaction.
9. Unsafe blocks, safe passes, and incomplete evidence becomes `UNVERIFIED`.
10. The decision and complete Change Passport are written back to DataHub idempotently.
11. Human-approved evidence becomes a reusable test or contract.
12. A second related change is caught by the remembered protection.
13. A new judge can reproduce the story from a fresh clone using public instructions.

The implementation is not complete until all thirteen criteria have recorded proof.

## Engineering invariants

1. Domain logic depends on typed ports; DataHub, GitHub, SQL engines, models, and agent
   runtimes are adapters.
2. Real DataHub is mandatory for integration and end-to-end proof. Recorded snapshots
   are permitted only for fast unit tests and a clearly labeled offline mode.
3. Entity identity is deterministic and ambiguous identity produces `UNVERIFIED`.
4. Empty, capped, stale, or unavailable lineage reduces Context Coverage; it never
   silently becomes “no impact.”
5. Every evaluation is deterministic or records enough parameters to replay it exactly.
6. Policy is rules-based, versioned, and separately testable from any reasoning model.
7. Write-back is idempotent, attributable, and safe to retry.
8. Accepted memory is human-approved, versioned, and reversible.
9. A no-LLM path completes the entire headline demo.
10. Secrets and sensitive row data never appear in committed fixtures, prompts, logs, or
    public reports.

## Scope boundary

The first winning slice supports one path exceptionally well: dbt/SQL on DuckDB to one
fraud feature table, one deterministic model, and one deterministic Fraud Review Agent.
New warehouses, orchestration systems, model frameworks, and agents plug into the same
ports later; they are not allowed to weaken the first end-to-end path.

The optional upstream/open-source contribution is a separate track owned by the project
author. Tripwire will expose reusable schemas and examples for it, but completion of the
core vertical slice does not depend on an upstream merge.

## Definition of done

A judge can open the hosted application or follow the quickstart, select the unsafe,
safe, and learned-protection scenarios, inspect the live DataHub-derived path, observe
old/new execution and the minimized witness, see the GitHub-style verdict, and verify the
idempotent memory in DataHub. The same commit and seed reproduce the same result without
private data or narration.
