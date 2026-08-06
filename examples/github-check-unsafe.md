# Blocked: executed evidence found a critical behavior change

**Verdict:** `UNSAFE`  
**Run:** `tw_adf492527c7b43fa1987fef4`  
**Context coverage:** `complete`  
**Critical evaluations:** 0 passed · 2 failed · 0 unresolved

## Why

- `CRITICAL_BEHAVIOR_REGRESSION`

## Concrete witness

Transaction `TX-009` reproduces the failure.

- Violated invariant: Replaying the same transaction must preserve the fraud model output and Fraud Review Agent action.
- Replay hash: `7769841c9ea349552c36d7e48e8e38f51a22cc1807c8dab0b931b84547bce78a`
- Minimization: 2 accepted of 5 attempted simplifications.
- Full before/after observations are preserved in the Change Passport.

## Failed consumers

- **Fraud Logistic Rule** — Model behavior changed for 2 transaction(s).
- **Fraud Review Agent** — Agent behavior changed for 2 transaction(s).

## Scope and limitations

- The Phase 1 evaluator covers the DuckDB fraud vertical slice only.
- Safety is bounded by the consumers and lineage returned in Context Coverage.
- Context provider was recorded-example-from-seeded-datahub, not live DataHub MCP.

---
Generated from executed evidence. Tripwire does not treat missing evidence as safe.
