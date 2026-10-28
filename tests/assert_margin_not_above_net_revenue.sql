-- Singular test: gross margin can never exceed net revenue
-- (that would imply a negative supply cost).
select
    order_line_sk,
    net_revenue,
    gross_margin
from {{ ref('fct_order_lines') }}
where gross_margin > net_revenue
