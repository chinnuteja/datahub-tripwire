# Tripwire proof bundle

These artifacts let reviewers inspect the headline proof without installing DataHub or
running the evaluator.

| Artifact | What it proves |
|---|---|
| [`github-check-unsafe.md`](github-check-unsafe.md) | The exact evidence report rendered for an `UNSAFE` GitHub Check. |
| [`minimized-witness-passport.json`](minimized-witness-passport.json) | A portable `TX-009` counterexample with executable minimization counts and a separately verifiable replay hash. |
| [`learned-loop/01-unsafe-semantic-passport.json`](learned-loop/01-unsafe-semantic-passport.json) | Live DataHub MCP context plus executed model/agent failures and witness `TX-009`. |
| [`learned-loop/02-active-protection.json`](learned-loop/02-active-protection.json) | The human-approved, versioned protection derived from that witness. |
| [`learned-loop/03-datahub-memory-receipt.json`](learned-loop/03-datahub-memory-receipt.json) | Stable DataHub URNs and affected assets proving the memory write-back. |
| [`learned-loop/04-learned-catch-passport.json`](learned-loop/04-learned-catch-passport.json) | A different SQL expression caught after DataHub returned the active protection. |
| [`contexts/fraud-feature-recorded.json`](contexts/fraud-feature-recorded.json) | An explicitly labeled offline context fixture for CI and local replay. |

Start with the [guided learned-loop narrative](learned-loop/README.md), then compare the
first and fourth Passports. The first run creates a proposed protection; the fourth shows
`LEARNED_PROTECTION_VIOLATED` after that approved knowledge is retrieved from DataHub.
Use `tripwire witness replay` with the minimized Passport to verify the witness in a new
process without trusting the original assessment run.
