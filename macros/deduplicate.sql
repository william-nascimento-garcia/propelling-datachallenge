{#
    Keeps exactly one row per business key.

    TPC-H has no duplicates today, but Bronze is a landing zone: in a real
    pipeline the same record can arrive twice (re-sent files, overlapping
    incremental loads, retries). Silver guarantees uniqueness so every model
    downstream can trust its keys; the unique tests in _silver__models.yml
    prove it on every run.

    The most recent version wins (latest _loaded_at, then latest _batch_id).

    Usage:
        with source as (
            {{ deduplicate(ref('brz_orders'), partition_by=['o_orderkey']) }}
        )
#}
{% macro deduplicate(relation, partition_by, order_by='_loaded_at desc, _batch_id desc') -%}
    select *
    from {{ relation }}
    qualify row_number() over (
        partition by {{ partition_by | join(', ') }}
        order by {{ order_by }}
    ) = 1
{%- endmacro %}
