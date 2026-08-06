-- A distinct code shape that violates the same future protection as unsafe_semantic.sql.
with normalized as (
    select
        *,
        case when device_age_days is null then 365 else device_age_days end as trusted_device_age
    from raw_transactions
),
scored as (
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
            when trusted_device_age < 7 then 0.18
            when trusted_device_age < 30 then 0.08
            else 0.00
        end
        + least(chargeback_count_30d, 2) * 0.12
        + case when customer_age_days < 30 then 0.08 else 0.00 end
        - case when is_refunded then 0.05 else 0.00 end as raw_fraud_signal
    from normalized
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
