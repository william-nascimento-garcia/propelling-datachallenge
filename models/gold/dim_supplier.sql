-- Columns dropped from slv_supplier:
--   supplier_address, phone,
--   phone_country_code           contact details with no analytical use (country comes from nation_name)
--   nation_id                    replaced by nation_name / region_name (denormalised geography)
--   _loaded_at                   technical column, not meaningful for BI users

with supplier as (
    select * from {{ ref('slv_supplier') }}
),

geography as (
    select * from {{ ref('slv_geography') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['supplier.supplier_id']) }}::varchar as supplier_sk,
    supplier.supplier_id::varchar                as supplier_id,
    supplier.supplier_name::varchar              as supplier_name,
    geography.nation_name::varchar               as nation_name,
    geography.region_name::varchar               as region_name,
    supplier.account_balance::number(12, 2)      as account_balance,
    supplier.has_negative_balance::boolean       as has_negative_balance
from supplier
left join geography
    on supplier.nation_id = geography.nation_id
