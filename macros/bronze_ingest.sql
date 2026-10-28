{#
    Standard Bronze landing pattern, reused by every Bronze model.

    Lands the source table exactly as-is (same column names, types and values)
    and appends technical lineage metadata. No business logic belongs here.

    Duplicate simulation (ON by default)
    ------------------------------------
    Real sources re-send data (retried extracts, overlapping incremental
    windows, files dropped twice). TPC-H never does, so to prove that the
    pipeline copes with it, every source row lands TWICE in Bronze by default.
    The second copy gets a later _loaded_at and a different _batch_id
    ('<invocation_id>-replay'); Silver's deduplicate() keeps one version per key.

    Effects you will see on every build:
      * Bronze tables have 2x the source rows
      * brz_lineitem's equal_rowcount test returns WARN (source vs Bronze differ)
      * Silver / Gold are identical to a clean load (unique + sum_matches pass)

        dbt build                                           # duplicated Bronze (default)
        dbt build --vars "{simulate_duplicates: false}"     # clean 1:1 Bronze
#}
{% macro bronze_ingest(source_name, table_name) -%}
{%- set simulate = var('simulate_duplicates', true) in [true, 'true', 'True', 1, '1'] -%}
select
    src.*,
    current_timestamp()::timestamp_ntz           as _loaded_at,
    '{{ invocation_id }}'                         as _batch_id,
    '{{ source(source_name, table_name) }}'       as _source_relation
from {{ source(source_name, table_name) }} as src
{%- if simulate %}

union all

-- Simulated re-delivery: same rows landing a second time (see macro header)
select
    src.*,
    dateadd(second, 1, current_timestamp())::timestamp_ntz  as _loaded_at,
    '{{ invocation_id }}-replay'                             as _batch_id,
    '{{ source(source_name, table_name) }}'                  as _source_relation
from {{ source(source_name, table_name) }} as src
{%- endif %}
{%- endmacro %}
