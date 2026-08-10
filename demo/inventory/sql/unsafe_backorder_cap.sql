-- Regression: the backorder contribution is capped one unit lower, which silently
-- understates stockout risk for every SKU with three or more open backorders.
-- Deliberately a different defect class from the fraud slice's null-handling change.
with scored as (
    select
        *,
        case
            when days_of_stock <= 3 then 0.34
            when days_of_stock <= 7 then 0.22
            when days_of_stock <= 14 then 0.10
            else 0.00
        end
        + case
            when coalesce(lead_time_days, 45) >= 30 then 0.20
            when coalesce(lead_time_days, 45) >= 14 then 0.10
            else 0.00
        end
        + case supplier_reliability when 'low' then 0.20 when 'medium' then 0.08 else 0.00 end
        + least(open_backorders, 2) * 0.09
        + case when is_seasonal then 0.07 else 0.00 end
        - case when is_discontinued then 0.12 else 0.00 end as raw_stockout_signal
    from raw_inventory
)

select
    sku_id,
    days_of_stock,
    lead_time_days,
    supplier_reliability,
    open_backorders,
    unit_cost_usd,
    is_seasonal,
    is_discontinued,
    round(greatest(0.0, least(1.0, raw_stockout_signal)), 6) as stockout_signal
from scored
order by sku_id
