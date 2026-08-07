# Passed within the evaluated scope

**Verdict:** `SAFE_WITHIN_SCOPE`
**Run:** `tw_6b6985ec511f50f768d56941`
**Context coverage:** `complete`
**Critical evaluations:** 3 passed · 0 failed · 0 unresolved

## Why

- `ALL_CRITICAL_EVALUATIONS_PASSED`

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

## Scope and limitations

- The Phase 1 evaluator covers the DuckDB fraud vertical slice only.
- Safety is bounded by the consumers and lineage returned in Context Coverage.

---
Generated from executed evidence. Tripwire does not treat missing evidence as safe.
