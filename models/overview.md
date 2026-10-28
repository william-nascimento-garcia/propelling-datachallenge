{% docs __overview__ %}
# TPC-H Commercial Performance: Medallion Architecture

An end-to-end **Bronze → Silver → Gold** data product built with **dbt** on **Snowflake**, using
`SNOWFLAKE_SAMPLE_DATA.TPCH_SF1` (a wholesale supplier: customers, orders, line items, parts and suppliers).

Use the **lineage graph** (blue button, bottom-right) to follow the data from the 8 TPC-H source tables
to the two dashboards that consume the Gold layer.

---

### Layers

| Layer | Schema | What happens | Rule |
|---|---|---|---|
| **Bronze** | `BRONZE` | Faithful copy of the 8 source tables plus `_loaded_at`, `_batch_id` and `_source_relation`. Every row lands **twice** to simulate a source re-sending data | No business logic. Tests only **warn** |
| **Silver** | `SILVER` | **Deduplication** (latest version per key), keys as strings, numbers as `NUMBER(p,s)`, business names, decoded codes, split composite attributes, conformed geography, reusable revenue rules | Use-case agnostic. Tests **block** the pipeline |
| **Gold** | `GOLD` | **Star schema**: `fct_order_lines` (one row per order line) with `dim_customer`, `dim_part`, `dim_supplier` and `dim_date` | Built for consumers. Contracts enforced |

### Analytical use case

**Commercial performance:** net revenue, discount and gross margin by customer, geography, product and time,
plus supplier delivery performance (late deliveries, returns, revenue at risk).

| Consumer | Questions answered |
|---|---|
| Commercial Director, Sales & Category Managers | Where do we make money? Where does discounting erode margin? Which regions, segments and brands grow? |
| Supply Chain / Procurement Manager | Which suppliers deliver late or get returns, and how much revenue is exposed? |

Gross margin is possible because `PARTSUPP` holds the supply cost of each part from each supplier.

### Quality

- **Keys:** `not_null` on every key and `unique` on every primary key in Silver and Gold.
- **Custom tests:** `is_positive`, `not_before` (chronology) and `sum_matches` (revenue reconciles between Silver and Gold).
- **Severity by layer:** Bronze warns (source issues are handled by Silver); Silver and Gold fail, because after deduplication a duplicate or null key can only be a bug.
- **Run log:** every run writes its results to `AUDIT.DBT_RUN_RESULTS`.
{% enddocs %}
