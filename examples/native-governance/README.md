# Native DataHub governance proof

Tripwire does not invent its own governance surface. It produces **executed evidence for
the primitives DataHub already ships** — Assertions and Incidents — so its findings land
where a data platform team is already looking.

Everything in this directory came out of a live DataHub OSS **v1.7.0** quickstart. Nothing
is hand-authored.

| Artifact | What it proves |
|---|---|
| [`01-unsafe-passport.json`](01-unsafe-passport.json) | The `UNSAFE` Change Passport: witness `TX-009`, two failed critical consumers, and a verified remediation. |
| [`02-active-protection.json`](02-active-protection.json) | The human-approved protection derived from that witness. |
| [`03-datahub-memory-receipt.json`](03-datahub-memory-receipt.json) | The write-back receipt, now carrying the **native** `assertion_urn`, `assertion_result`, `incident_urn`, and `incident_state`. |
| [`04-datahub-graphql-proof.json`](04-datahub-graphql-proof.json) | The response from **DataHub's own GraphQL API** — the exact query its UI issues to render the Validation and Incidents tabs. |

## The mapping

| Tripwire concept | DataHub primitive it writes |
|---|---|
| Human-approved Protection | **Assertion** (`CUSTOM` / `TRIPWIRE_PROTECTION`), invariant as its logic |
| Each assessment that ran it | **`assertionRunEvent`** keyed by the Tripwire run ID — real pass/fail history |
| `UNSAFE` verdict | **Incident**, `ACTIVE`, naming the changed asset and every critical consumer |
| A later `SAFE_WITHIN_SCOPE` run on the same asset | The **same** Incident, `RESOLVED` |
| `UNVERIFIED` verdict | **Nothing.** Tripwire proved nothing, so it asserts nothing. |

## Two honesty rules encoded here

**An available fix is not a resolution.** The incident in this bundle stays `ACTIVE` even
though Tripwire found and *verified* a repair, because nobody applied it. Its message says
so exactly:

> `Opened by Tripwire run tw_377cfdf2ecc47468fda1f1ef. A verified fix is available (fix_e441728a2dfcf687) but has not been applied.`

Only an executed assessment that comes back safe closes it. The incident is therefore keyed
on the **changed asset**, not the run — one asset owns one incident that can genuinely open
and close over time.

**A protection's first recorded run is its real failure.** A protection is born from a
witness, so its first `assertionRunEvent` records that witness `FAILURE` rather than a
synthetic pass it never earned.

## Reproduce it

With a live DataHub quickstart running:

```powershell
uv run tripwire assess --candidate unsafe_semantic `
  --context-file examples/contexts/fraud-feature-recorded.json `
  --output artifacts/runtime/unsafe.json
uv run tripwire protection approve --passport artifacts/runtime/unsafe.json `
  --approved-by urn:li:corpuser:fraud-platform
```

Then open the dataset in DataHub and check the **Validation** and **Incidents** tabs:

```
http://localhost:9002/dataset/urn:li:dataset:(urn:li:dataPlatform:duckdb,tripwire_fraud.fraud.fct_fraud_features,PROD)
```
