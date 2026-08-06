# Tripwire Fraud Demonstration World

This directory is a public, deterministic miniature production path:

```text
raw_transactions → fct_fraud_features → fraud-logistic-rule/1.0.0
                 → fraud-review-agent/1.0.0 → approve/review/block
```

The CSV contains synthetic data only. `TX-009` is a deliberately useful boundary case:
the baseline treats an unknown device age as new/risky, while `unsafe_semantic.sql`
incorrectly treats it as old/trusted. The SQL is not told that this row is special; the
model and agent discover the behavior from normal execution.

Run the baseline:

```powershell
.\.venv\Scripts\tripwire.exe demo build --scenario baseline
```

Build the dbt project and its real `manifest.json`:

```powershell
.\.venv\Scripts\dbt.exe build --project-dir demo/fraud --profiles-dir demo/fraud
```
