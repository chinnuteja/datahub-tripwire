-- Mechanical break: the model contract requires fraud_signal, but this alias removes it.
select
    transaction_id,
    amount_usd,
    is_international,
    merchant_risk,
    customer_age_days,
    device_age_days,
    chargeback_count_30d,
    is_refunded,
    0.0 as risk_signal
from raw_transactions
order by transaction_id
