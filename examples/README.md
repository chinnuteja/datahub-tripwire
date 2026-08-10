# Tripwire proof bundle

These artifacts let reviewers inspect the headline proof without installing DataHub or
running the evaluator.

| Artifact | What it proves |
|---|---|
| [`live-v2/README.md`](live-v2/README.md) | Current-commit live DataHub MCP proof: v2 model inheritance, current Passport write-back, a distinct learned catch, and a safe control through the same graph. |
| [`public-proof/unsafe-pr-passport.json`](public-proof/unsafe-pr-passport.json) | Exact public PR base/head SQL produced `UNSAFE`, witness `TX-009`, explicit coverage and owner routing, plus an executed verified repair. |
| [`public-proof/safe-pr-passport.json`](public-proof/safe-pr-passport.json) | A different public PR produced `SAFE_WITHIN_SCOPE`, 3/3 metadata operations, 2/2 critical consumers evaluated, and no witness. |
| [`public-proof/unsafe-pr-check.md`](public-proof/unsafe-pr-check.md) | The judge-readable Check report containing the verified SQL patch and restored model/agent evaluations. |
| [`public-proof/safe-pr-check.md`](public-proof/safe-pr-check.md) | The corresponding green Check report for the safe additive change. |
| [`github-check-unsafe.md`](github-check-unsafe.md) | The exact evidence report rendered for an `UNSAFE` GitHub Check. |
| [`minimized-witness-passport.json`](minimized-witness-passport.json) | A portable `TX-009` counterexample with executable minimization counts and a separately verifiable replay hash. |
| [`learned-loop/01-unsafe-semantic-passport.json`](learned-loop/01-unsafe-semantic-passport.json) | Live DataHub MCP context plus executed model/agent failures and witness `TX-009`. |
| [`learned-loop/02-active-protection.json`](learned-loop/02-active-protection.json) | The human-approved, versioned protection derived from that witness. |
| [`learned-loop/03-datahub-memory-receipt.json`](learned-loop/03-datahub-memory-receipt.json) | Stable DataHub URNs and affected assets proving the memory write-back. |
| [`learned-loop/04-learned-catch-passport.json`](learned-loop/04-learned-catch-passport.json) | A different SQL expression caught after DataHub returned the active protection. |
| [`contexts/fraud-feature-recorded.json`](contexts/fraud-feature-recorded.json) | An explicitly labeled offline context fixture for CI and local replay. |
| [`native-governance/README.md`](native-governance/README.md) | **Tripwire's findings as native DataHub Assertions and Incidents**, captured from DataHub's own GraphQL API on a live v1.7.0 stack. |
| [`inventory-slice-passport.json`](inventory-slice-passport.json) | A **second, unrelated domain** — inventory stockout risk — producing `UNSAFE` and witness `SKU-0102` through the same evaluator, with its own schema, model artifact, and agent. |

## The evaluator is not fraud-specific

`inventory-slice-passport.json` is the answer to "does this only work on your demo?" The
inventory slice shares zero evaluator code with fraud. It declares only a `SliceSpec`:

| | Fraud slice | Inventory slice |
|---|---|---|
| Input table | `raw_transactions` (8 cols) | `raw_inventory` (8 different cols) |
| Record key | `transaction_id` | `sku_id` |
| Model | `fraud-risk-calibrator/2.0.0` | `stockout-risk-classifier/1.0.0` |
| Agent | `fraud-review-agent/1.0.0` | `replenishment-agent/1.0.0` |
| Defect class | null handling (`coalesce`) | boundary cap (`least(..., 3)` → `2`) |
| Result | `UNSAFE`, witness `TX-009` | `UNSAFE`, witness `SKU-0102` |

Reproduce it in one command:

```powershell
uv run tripwire assess --slice inventory --candidate unsafe_backorder_cap `
  --context-file examples/contexts/inventory-feature-recorded.json `
  --output artifacts/runtime/inventory.json --requested-by judge
```

The two slices deliberately use *different defect classes*, so the second one is not a
rename of the first: the fraud regression hides risk by mis-handling NULLs, and the
inventory regression hides risk by lowering an aggregation cap. Both are caught by
execution, not by pattern matching.

Note on field names: the shared evidence contract still calls its record key
`transaction_id` and its positive-class flag `predicted_fraud`. Those are the fraud
slice's names, retained deliberately so that every previously published Change Passport
stays byte-verifiable against the current engine. Generalizing them is a schema 2.0
change, not a demo change.

Start with the [current live v2 proof](live-v2/README.md), then use the original
[guided learned-loop narrative](learned-loop/README.md) to inspect how the inherited
protection was first created. Together they show that DataHub memory survives a model
upgrade and continues protecting later changes.
Use `tripwire witness replay` with the minimized Passport to verify the witness in a new
process without trusting the original assessment run.
