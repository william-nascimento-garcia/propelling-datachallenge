/* Queries to run live in Snowsight during the demo, as the REPORTER role,
   proving the Gold layer is consumption-ready (no transformation needed). */

-- 0. Layers are visible and populated (as TRANSFORMER, which sees all layers)
USE ROLE TRANSFORMER;
USE WAREHOUSE WH_TRANSFORM;
SELECT table_schema, table_name, row_count
FROM TPCH_ANALYTICS.INFORMATION_SCHEMA.TABLES
WHERE table_schema IN ('BRONZE', 'SILVER', 'GOLD')
ORDER BY table_schema, table_name;

-- From here on: the BI consumer's point of view (only GOLD is visible)
USE ROLE REPORTER;
USE WAREHOUSE WH_REPORTING;
USE SCHEMA TPCH_ANALYTICS.GOLD;

-- 1. Revenue and margin by customer region and year
SELECT d.year_number, c.region_name,
       SUM(f.net_revenue)  AS net_revenue,
       SUM(f.gross_margin) AS gross_margin,
       DIV0(SUM(f.gross_margin), SUM(f.net_revenue)) AS gross_margin_pct
FROM fct_order_lines f
LEFT JOIN dim_customer c ON f.customer_sk = c.customer_sk
LEFT JOIN dim_date d     ON f.order_date_key = d.date_key
GROUP BY ALL ORDER BY 1, 2;

-- 2. Where does discounting hurt margin the most?
SELECT c.market_segment,
       SUM(f.discount_amount) AS discount_given,
       DIV0(SUM(f.discount_amount), SUM(f.gross_sales_amount)) AS effective_discount_rate,
       DIV0(SUM(f.gross_margin), SUM(f.net_revenue))           AS gross_margin_pct
FROM fct_order_lines f
LEFT JOIN dim_customer c ON f.customer_sk = c.customer_sk
GROUP BY ALL ORDER BY discount_given DESC;

-- 3. Suppliers with the worst late-delivery rate, and revenue at risk
SELECT s.supplier_name, s.nation_name,
       DIV0(COUNT_IF(f.is_late_delivery), COUNT(*)) AS late_delivery_rate,
       SUM(IFF(f.is_late_delivery, f.net_revenue, 0)) AS late_net_revenue
FROM fct_order_lines f
LEFT JOIN dim_supplier s ON f.supplier_sk = s.supplier_sk
WHERE f.is_received
GROUP BY ALL
HAVING COUNT(*) >= 100
ORDER BY late_delivery_rate DESC
LIMIT 10;

-- 4. Top 10 brands by margin
SELECT p.brand, SUM(f.gross_margin) AS gross_margin
FROM fct_order_lines f LEFT JOIN dim_part p ON f.part_sk = p.part_sk
GROUP BY ALL ORDER BY gross_margin DESC LIMIT 10;
