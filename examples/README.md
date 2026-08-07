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

Start with the [current live v2 proof](live-v2/README.md), then use the original
[guided learned-loop narrative](learned-loop/README.md) to inspect how the inherited
protection was first created. Together they show that DataHub memory survives a model
upgrade and continues protecting later changes.
Use `tripwire witness replay` with the minimized Passport to verify the witness in a new
process without trusting the original assessment run.
