---
name: tripwire-change-safety
description: Assess real SQL or dbt changes against DataHub schema, lineage, ownership, ML-model, and AI-agent context. Use when an agent must prove whether a proposed data-code change is safe, produce a concrete counterexample and verified repair for an unsafe change, fail closed when evidence is incomplete, publish a GitHub Check, or turn a human-approved failure witness into reusable DataHub protection memory.
---

# Tripwire Change Safety

Use Tripwire from the repository root. Preserve exact revisions, URNs, tool versions,
and generated evidence; never replace execution with a prose-only risk opinion.

## Preconditions

1. Confirm `uv.lock`, `demo/fraud`, and `tripwire` exist.
2. Run `uv sync --frozen --extra dev` when the locked environment is not installed.
3. Use live DataHub MCP by default. Use `--context-file` only when the user explicitly
   requests offline replay or live DataHub is unavailable, and label the result recorded.
4. Create output paths under `artifacts/runtime`; do not commit that runtime directory.

For the included local DataHub vertical slice, run the platform-specific
`scripts/bootstrap-phase1` script. It starts DataHub v1.7, builds dbt, seeds the graph,
lists the official MCP tools, and preserves the complete live Context Snapshot.

## Assess an exact Git change

Require all of these inputs:

- base Git revision;
- candidate Git revision;
- exact changed dbt SQL path;
- compiled dbt `manifest.json`;
- project directory.

Compile the manifest before assessment, then run:

```text
uv run dbt compile --project-dir <project-dir> --profiles-dir <profiles-dir>
uv run tripwire assess-git \
  --base-ref <base-revision> \
  --head-ref <candidate-revision> \
  --changed-path <exact-model.sql> \
  --manifest-path <manifest.json> \
  --project-dir <project-dir> \
  --output artifacts/runtime/change-passport.json \
  --requested-by <actor>
```

Do not guess among multiple changed models. Let Tripwire stop with `UNVERIFIED` when
revision loading, AST analysis, dbt resolution, context identity, or MCP coverage is
ambiguous.

## Interpret the Change Passport

When you invoke the CLI, treat the process exit and Passport verdict together:

| Exit | Verdict | Required action |
|---|---|---|
| `0` | `SAFE_WITHIN_SCOPE` | Report the declared scope, completed metadata operations, and passed critical consumers. Never shorten this to unqualified "safe." |
| `1` | `UNSAFE` | Report failed consumers, the minimized witness, owner route, and verified remediation when present. Block the change. |
| `2` | `UNVERIFIED` | Report the exact evidence gap or runtime failure. Never convert missing evidence into success. |

When auditing a persisted Passport without its process log, validate the complete
Passport contract and state that the original exit was not independently observed. Do
not override an otherwise valid bounded verdict solely because an external exit code was
not stored in the JSON.

Before presenting a result, verify:

- `run.commit_sha` identifies the executing engine revision;
- `resolved_entity.urn` is the exact dbt/DataHub entity;
- coverage operations and critical-consumer counts reconcile;
- every critical consumer has an executed evaluation;
- model evaluations record model version, artifact SHA-256, and replayed rows;
- owner routes came from DataHub facts;
- a remediation is described as verified only when it includes a fixed output hash and
  restored evaluation IDs;
- limitations remain visible.

Render the same report used by the GitHub adapter:

```text
uv run tripwire github render \
  --passport artifacts/runtime/change-passport.json \
  --output artifacts/runtime/tripwire-check.md
```

## Publish a GitHub Check

Publish only when the user authorized the repository and commit. Require
`GITHUB_TOKEN`, exact `owner/name`, and exact head SHA:

```text
uv run tripwire github publish \
  --passport artifacts/runtime/change-passport.json \
  --repository <owner/name> \
  --head-sha <head-sha> \
  --details-url <evidence-url>
```

Confirm the resulting Check conclusion matches the Passport. A successful workflow
that publishes an unsafe `failure` Check is correct behavior.

## Create durable protection memory

Never approve a proposed protection autonomously. After a human supplies an exact
DataHub corpuser URN, publish the approval:

```text
uv run tripwire protection approve \
  --passport artifacts/runtime/change-passport.json \
  --approved-by urn:li:corpuser:<reviewer> \
  --output artifacts/runtime/active-protection.json
```

Preserve the active protection and `datahub-memory-receipt.json`. Verify the receipt
contains stable Passport and protection URNs, the affected entities, payload hash, and
publication time. Reassess a distinct related change through live DataHub and require
`LEARNED_PROTECTION_VIOLATED` to prove the next agent inherited the knowledge.

## Independent witness verification

Replay an unsafe witness in a fresh process using the exact old and new SQL:

```text
uv run tripwire witness replay \
  --passport artifacts/runtime/change-passport.json \
  --baseline-sql <baseline.sql> \
  --candidate-sql <candidate.sql>
```

Accept the witness only when `replay_hash_verified` is true and the reproduced actions
match the Passport.

## Guardrails

- Do not claim safety from metadata lookup alone.
- Do not silently substitute recorded context for live MCP.
- Do not publish to a repository, commit, or DataHub instance the user did not place in
  scope.
- Do not hide cancelled or skipped evaluations.
- Do not write protection memory without explicit human approval.
- Do not remove limitations, scope accounting, provenance, or owner routing from judge-
  facing output.
