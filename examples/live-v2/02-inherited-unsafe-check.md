# Blocked: executed evidence found a critical behavior change

**Verdict:** `UNSAFE`
**Run:** `tw_0f4441f5d063ef2f937540e2`
**Context coverage:** `complete`
**Critical evaluations:** 0 passed · 3 failed · 0 unresolved

## Why

- `LEARNED_PROTECTION_VIOLATED`

## Evidence coverage

- Metadata operations: **3/3**
- Critical consumers evaluated: **2/2**
- Unresolved context gaps: **0**
- Lineage frontier complete: **yes**

## Executed consumer identity

- Model version: `fraud-risk-calibrator/2.0.0`
- Model artifact SHA-256: `7d7edecb0868ae9fc068c5c73679b261f51e71bc2099f2fc0b6fd7887b9f89f6`
- Rows replayed: **12**

## Required review routing

- **Fraud Platform Team** (`urn:li:corpuser:fraud-platform`) — 3 affected asset(s)

## Concrete witness

Transaction `TX-009` reproduces the failure.

- Violated invariant: Replaying the same transaction must preserve the fraud model output and Fraud Review Agent action.
- Replay hash: `3ba94da21c5dcf2a524ec048f64d5e0347474f9576c4f05e7aa587693b61422d`
- Minimization: 2 accepted of 5 attempted simplifications.
- Full before/after observations are preserved in the Change Passport.

## Failed consumers

- **fraud_logistic_rule** — Model behavior changed for 2 transaction(s).
- **Fraud Review Agent** — Agent behavior changed for 2 transaction(s).
- **Fraud Features** — Candidate violates a human-approved learned protection.

## Scope and limitations

- The Phase 1 evaluator covers the DuckDB fraud vertical slice only.
- Safety is bounded by the consumers and lineage returned in Context Coverage.

---
Generated from executed evidence. Tripwire does not treat missing evidence as safe.
