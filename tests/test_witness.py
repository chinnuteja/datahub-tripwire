from pathlib import Path

from tripwire.demo.fraud import load_transactions, replay_fraud_transaction
from tripwire.witness import minimize_fraud_witness

DEMO = Path("demo/fraud")


def test_counterexample_is_simplified_by_executable_replay() -> None:
    transaction = next(
        row
        for row in load_transactions(DEMO / "seeds" / "raw_transactions.csv")
        if row["transaction_id"] == "TX-009"
    )
    baseline_sql = (DEMO / "sql" / "baseline.sql").read_text(encoding="utf-8")
    candidate_sql = (DEMO / "sql" / "unsafe_semantic.sql").read_text(encoding="utf-8")

    witness = minimize_fraud_witness(
        transaction=transaction,
        baseline_sql=baseline_sql,
        candidate_sql=candidate_sql,
    )

    assert transaction["amount_usd"] == 520.0
    assert transaction["customer_age_days"] == 90
    assert witness.transaction["amount_usd"] == 500.0
    assert witness.transaction["customer_age_days"] == 30
    assert witness.transaction["device_age_days"] is None
    assert witness.baseline.action.value == "review"
    assert witness.candidate.action.value == "approve"
    assert witness.accepted_simplifications == 2
    assert witness.attempted_simplifications >= 5


def test_each_remaining_risk_dimension_is_necessary_for_action_flip() -> None:
    baseline_sql = (DEMO / "sql" / "baseline.sql").read_text(encoding="utf-8")
    candidate_sql = (DEMO / "sql" / "unsafe_semantic.sql").read_text(encoding="utf-8")
    minimal = {
        "transaction_id": "TX-MIN",
        "amount_usd": 500.0,
        "is_international": True,
        "merchant_risk": "medium",
        "customer_age_days": 30,
        "device_age_days": None,
        "chargeback_count_30d": 0,
        "is_refunded": False,
    }

    for field, neutral in (
        ("amount_usd", 0.0),
        ("is_international", False),
        ("merchant_risk", "low"),
        ("device_age_days", 30),
    ):
        trial = {**minimal, field: neutral}
        before = replay_fraud_transaction(sql=baseline_sql, transaction=trial)
        after = replay_fraud_transaction(sql=candidate_sql, transaction=trial)
        assert before.action == after.action, field
