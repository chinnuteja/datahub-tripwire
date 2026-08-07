# Live DataHub v2 proof

This bundle was produced on commit
`b394df6b6274afe37bdb003ee3012211c6bceab7` against a healthy local DataHub
v1.7.0 stack through the official `mcp-server-datahub` 0.6.0 tools. It is the
judge-inspectable proof that Tripwire's memory survives a model upgrade.

The sequence is intentionally longitudinal:

1. [`01-datahub-context.json`](01-datahub-context.json) is the complete live MCP
   snapshot: three source-hashed facts, five lineage paths, two critical consumers,
   DataHub ownership, and one human-approved protection inherited from the earlier
   `TX-009` incident.
2. [`02-inherited-unsafe-passport.json`](02-inherited-unsafe-passport.json) executes
   the semantic regression through `fraud-risk-calibrator/2.0.0`. All three critical
   evaluations fail and the inherited protection produces
   `LEARNED_PROTECTION_VIOLATED`. The compact Check report is
   [`02-inherited-unsafe-check.md`](02-inherited-unsafe-check.md).
3. [`03-active-protection.json`](03-active-protection.json) preserves the exact
   human approval and portable counterexample fixture.
4. [`04-datahub-writeback-receipt.json`](04-datahub-writeback-receipt.json) proves
   that the current v2 Change Passport was written to a stable DataHub URN and the
   protection was attached to all three affected entities.
5. [`05-related-change-catch-passport.json`](05-related-change-catch-passport.json)
   proves a distinct related SQL expression is caught by the inherited memory.
6. [`06-safe-control-passport.json`](06-safe-control-passport.json) runs a safe
   additive change through the same live graph, model, agent, and protection. All
   three critical evaluations pass and the verdict is `SAFE_WITHIN_SCOPE`. Its
   compact report is [`06-safe-control-check.md`](06-safe-control-check.md).
7. [`07-seed-manifest.json`](07-seed-manifest.json) binds the ten seeded DataHub
   entities to the exact dbt manifest and graph version.
8. [`08-model-replay.json`](08-model-replay.json) records the 12-row executable
   logistic-model replay and its model artifact hash.

Nothing in this directory is a hand-authored verdict. The Passports validate against
Tripwire's public schema, carry the exact engine commit, and contain the raw MCP facts
used to select downstream evaluations.
