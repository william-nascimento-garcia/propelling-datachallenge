-- Customer dimension, denormalised with geography (star schema: no
-- snowflaking into nation/region tables, so BI tools need one join).
-- The street address is deliberately left out: it is PII with no analytical use.

-- Columns dropped from slv_customer:
--   customer_address, phone      PII with no analytical use (data minimisation in the consumption layer)
--   nation_id                    replaced by nation_name / region_name (denormalised geography)
--   _loaded_at                   technical column, not meaningful for BI users

with customer as (
    select * from {{ ref('slv_customer') }}
),

geography as (
    select * from {{ ref('slv_geography') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['customer.customer_id']) }}::varchar as customer_sk,
    customer.customer_id::varchar                as customer_id,
    customer.customer_name::varchar              as customer_name,
    customer.market_segment::varchar             as market_segment,
    geography.nation_name::varchar               as nation_name,
    geography.region_name::varchar               as region_name,
    customer.phone_country_code::number(38, 0)   as phone_country_code,
    customer.account_balance::number(12, 2)      as account_balance,
    case
        when customer.account_balance < 0 then '1. Negative'
        when customer.account_balance < 2500 then '2. 0 - 2.5k'
        when customer.account_balance < 5000 then '3. 2.5k - 5k'
        when customer.account_balance < 7500 then '4. 5k - 7.5k'
        else '5. 7.5k+'
    end::varchar                                 as account_balance_band,
    customer.has_negative_balance::boolean       as has_negative_balance
from customer
left join geography
    on customer.nation_id = geography.nation_id
