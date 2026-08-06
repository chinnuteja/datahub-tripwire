with scored as (
    select
        *,
        case
            when amount_usd >= 1000 then 0.30
            when amount_usd >= 500 then 0.18
            when amount_usd >= 200 then 0.08
            else 0.00
        end
        + case when is_international then 0.18 else 0.00 end
        + case merchant_risk when 'high' then 0.22 when 'medium' then 0.08 else 0.00 end
        + case
            when coalesce(device_age_days, 0) < 7 then 0.18
            when coalesce(device_age_days, 0) < 30 then 0.08
            else 0.00
        end
        + least(chargeback_count_30d, 2) * 0.12
        + case when customer_age_days < 30 then 0.08 else 0.00 end
        - case when is_refunded then 0.05 else 0.00 end as raw_fraud_signal
    from raw_transactions
)

select
    transaction_id,
    amount_usd,
    is_international,
    merchant_risk,
    customer_age_days,
    device_age_days,
    chargeback_count_30d,
    is_refunded,
    round(greatest(0.0, least(1.0, raw_fraud_signal)), 6) as fraud_signal
from scored
order by transaction_id
