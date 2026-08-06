# Live learned-protection proof

These artifacts were produced against the seeded DataHub v1.7.0 graph through the
official `mcp-server-datahub==0.6.0` server.

1. `01-unsafe-semantic-passport.json` proves the first behavioral regression and proposes
   witness `TX-009` as reusable protection.
2. `02-active-protection.json` records explicit human approval and immutable provenance.
3. `03-datahub-memory-receipt.json` identifies the Passport, Protection, tag, and affected
   entities written to DataHub.
4. `04-learned-catch-passport.json` shows a distinct later SQL change retrieving and
   violating the active protection with reason `LEARNED_PROTECTION_VIOLATED`.

All transaction data is deterministic and synthetic.
