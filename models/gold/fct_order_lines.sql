{{ config(cluster_by=['order_date_key']) }}

-- Columns dropped (and why):
--   slv_lineitem.part_id, supplier_id  replaced by part_sk / supplier_sk (joins go through the dimensions)
--   slv_lineitem.ship/commit/receipt_date  replaced by *_date_key (join to dim_date for any calendar attribute)
--   slv_lineitem.ship_instruction  operational detail, outside the commercial use case
--   slv_orders.customer_id       replaced by customer_sk
--   slv_orders.order_date        replaced by order_date_key
--   slv_orders.order_total_price order-header total: repeating it on every line would double count when summed
--   slv_orders.clerk_id, ship_priority  not used by the use case (ship_priority is always 0 in TPC-H)
--   slv_partsupp.available_quantity, part_supplier_id  stock snapshot / technical key, not part of a sales event
--   _loaded_at                   technical column, not meaningful for BI users
-- Columns renamed for business users:
--   extended_price -> gross_sales_amount, net_amount -> net_revenue,
--   gross_amount_with_tax -> invoiced_amount

-- Grain: one row per order line (order_id + line_number).
-- Central fact of the commercial performance star schema.
-- Order header attributes (status, priority) are kept as degenerate dimensions.
-- Margin uses the supplier's unit supply cost for that exact part (PARTSUPP).
-- All joins are LEFT joins: a line is never silently dropped because a lookup is
-- missing. An orphan shows up as a NULL key and fails the not_null tests on the keys,
-- and the equal_rowcount + sum_matches tests prove no line was lost or duplicated.

with lines as (
    select * from {{ ref('slv_lineitem') }}
),

orders as (
    select * from {{ ref('slv_orders') }}
),

part_supplier as (
    select * from {{ ref('slv_partsupp') }}
),

customers as (
    select
        customer_sk,
        customer_id
    from {{ ref('dim_customer') }}
),

parts as (
    select
        part_sk,
        part_id
    from {{ ref('dim_part') }}
),

suppliers as (
    select
        supplier_sk,
        supplier_id
    from {{ ref('dim_supplier') }}
),

joined as (
    select
        lines.*,
        orders.order_date,
        orders.order_status,
        orders.order_priority,
        orders.order_priority_rank,
        customers.customer_sk,
        parts.part_sk,
        suppliers.supplier_sk,
        part_supplier.supply_cost                             as unit_supply_cost,
        round(part_supplier.supply_cost * lines.quantity, 2)  as supply_cost_amount
    from lines
    left join orders
        on lines.order_id = orders.order_id
    left join part_supplier
        on
            lines.part_id = part_supplier.part_id
            and lines.supplier_id = part_supplier.supplier_id
    left join customers
        on orders.customer_id = customers.customer_id
    left join parts
        on lines.part_id = parts.part_id
    left join suppliers
        on lines.supplier_id = suppliers.supplier_id
)

select
    -- keys
    order_line_id::varchar                                       as order_line_sk,
    customer_sk::varchar                                         as customer_sk,
    part_sk::varchar                                             as part_sk,
    supplier_sk::varchar                                         as supplier_sk,
    to_char(order_date, 'YYYYMMDD')::varchar                     as order_date_key,
    to_char(ship_date, 'YYYYMMDD')::varchar                      as ship_date_key,
    to_char(commit_date, 'YYYYMMDD')::varchar                    as commit_date_key,
    to_char(receipt_date, 'YYYYMMDD')::varchar                   as receipt_date_key,

    -- degenerate dimensions
    order_id::varchar                                            as order_id,
    line_number::number(38, 0)                                   as line_number,
    order_status::varchar                                        as order_status,
    order_priority::varchar                                      as order_priority,
    order_priority_rank::number(38, 0)                           as order_priority_rank,
    line_status::varchar                                         as line_status,
    return_status::varchar                                       as return_status,
    ship_mode::varchar                                           as ship_mode,

    -- additive measures
    quantity::number(12, 2)                                      as quantity,
    extended_price::number(14, 2)                                as gross_sales_amount,
    discount_amount::number(14, 2)                               as discount_amount,
    net_amount::number(14, 2)                                    as net_revenue,
    (gross_amount_with_tax - net_amount)::number(14, 2)          as tax_amount,
    gross_amount_with_tax::number(14, 2)                         as invoiced_amount,
    supply_cost_amount::number(14, 2)                            as supply_cost_amount,
    (net_amount - supply_cost_amount)::number(14, 2)             as gross_margin,

    -- non-additive measures (average them, never sum)
    discount_rate::number(5, 4)                                  as discount_rate,
    tax_rate::number(5, 4)                                       as tax_rate,
    unit_supply_cost::number(12, 2)                              as unit_supply_cost,
    delivery_delay_days::number(38, 0)                           as delivery_delay_days,
    transit_days::number(38, 0)                                  as transit_days,

    -- flags
    is_received::boolean                                         as is_received,
    is_late_delivery::boolean                                    as is_late_delivery,
    is_returned::boolean                                         as is_returned
from joined
