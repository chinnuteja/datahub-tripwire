# Blocked: executed evidence found a critical behavior change

**Verdict:** `UNSAFE`  
**Run:** `tw_bbed61fa4e9236d3a1956448`  
**Context coverage:** `complete`  
**Critical evaluations:** 0 passed · 2 failed · 0 unresolved

## Why

- `CRITICAL_BEHAVIOR_REGRESSION`

## Evidence coverage

- Metadata operations: **3/3**
- Critical consumers evaluated: **2/2**
- Unresolved context gaps: **0**
- Lineage frontier complete: **yes**

## Required review routing

- **Fraud Platform Team** (`urn:li:corpuser:fraud-platform`) — 1 affected asset(s)

## Concrete witness

Transaction `TX-009` reproduces the failure.

- Violated invariant: Replaying the same transaction must preserve the fraud model output and Fraud Review Agent action.
- Replay hash: `7769841c9ea349552c36d7e48e8e38f51a22cc1807c8dab0b931b84547bce78a`
- Minimization: 2 accepted of 5 attempted simplifications.
- Full before/after observations are preserved in the Change Passport.

## Failed consumers

- **Fraud Logistic Rule** — Model behavior changed for 2 transaction(s).
- **Fraud Review Agent** — Agent behavior changed for 2 transaction(s).

## Executed remediation

**Status:** `verified`  
Restore the baseline null-handling semantics; Tripwire replayed the repair and recovered identical model predictions and agent decisions.

- Remediation: `fix_1f2883b353f78e0b`
- Restored evaluations: model-1, agent-2
- Fixed output hash: `79f83b0cf28a2dad9719457157bcf6a4515c2fd24205fbc25c6143e08c887af2`

```diff
--- candidate.sql
+++ tripwire-verified-fix.sql
@@ -11,8 +11,8 @@
         + case when is_international then 0.18 else 0.00 end
         + case merchant_risk when 'high' then 0.22 when 'medium' then 0.08 else 0.00 end
         + case
-            when coalesce(device_age_days, 365) < 7 then 0.18
-            when coalesce(device_age_days, 365) < 30 then 0.08
+            when COALESCE(device_age_days, 0) < 7 then 0.18
+            when COALESCE(device_age_days, 0) < 30 then 0.08
             else 0.00
         end
         + least(chargeback_count_30d, 2) * 0.12
```

## Scope and limitations

- The Phase 1 evaluator covers the DuckDB fraud vertical slice only.
- Safety is bounded by the consumers and lineage returned in Context Coverage.
- Context provider was recorded-example-from-seeded-datahub, not live DataHub MCP.

---
Generated from executed evidence. Tripwire does not treat missing evidence as safe.
