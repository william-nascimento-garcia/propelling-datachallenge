-- Columns dropped from slv_part:
--   _loaded_at                   technical column, not meaningful for BI users

select
    {{ dbt_utils.generate_surrogate_key(['part_id']) }}::varchar as part_sk,
    part_id::varchar                as part_id,
    part_name::varchar              as part_name,
    manufacturer::varchar           as manufacturer,
    brand::varchar                  as brand,
    part_type::varchar              as part_type,
    part_class::varchar             as part_class,
    part_finish::varchar            as part_finish,
    part_material::varchar          as part_material,
    part_size::number(38, 0)        as part_size,
    container::varchar              as container,
    container_size::varchar         as container_size,
    container_type::varchar         as container_type,
    retail_price::number(12, 2)     as retail_price
from {{ ref('slv_part') }}
