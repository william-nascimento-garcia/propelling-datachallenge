{#
    Run log: writes one row per executed node (model, test, seed, snapshot) to
    <database>.AUDIT.DBT_RUN_RESULTS at the end of every dbt invocation.

    Wired in dbt_project.yml:
        on-run-end:
          - "{{ log_run_results(results) }}"

    Design choices
      * Structured data, not log text: it reads the same `results` object that
        dbt writes to target/run_results.json.
      * One shared AUDIT schema for every target (dev / ci / prod); the
        target_name column tells them apart, so CI history survives even though
        the CI_PR_* schemas are dropped after each pull request.
      * Kept outside the medallion layers (not a model), so it does not appear
        in the lineage graph.
      * Only for commands that execute nodes (build / run / test / seed / snapshot).
#}

{% macro log_run_results(results) %}
    {% if not execute or not results %}
        {{ return('') }}
    {% endif %}
    {% if flags.WHICH not in ['build', 'run', 'test', 'seed', 'snapshot'] %}
        {{ return('') }}
    {% endif %}

    {% set audit_relation = target.database ~ '.AUDIT.DBT_RUN_RESULTS' %}

    {% set create_schema %}
        create schema if not exists {{ target.database }}.AUDIT
            comment = 'Operational metadata: dbt run history (not a medallion layer)'
    {% endset %}
    {% do run_query(create_schema) %}

    {% set ddl %}
        create table if not exists {{ audit_relation }} (
            invocation_id     varchar,
            command           varchar,
            target_name       varchar,
            dbt_version       varchar,
            run_started_at    timestamp_tz,
            logged_at         timestamp_ntz default current_timestamp()::timestamp_ntz,
            node_id           varchar,
            node_name         varchar,
            resource_type     varchar,
            schema_name       varchar,
            status            varchar,
            execution_time_s  number(10, 3),
            rows_affected     number(38, 0),
            failures          number(38, 0),
            query_id          varchar,
            message           varchar
        )
    {% endset %}
    {% do run_query(ddl) %}

    {% set rows = [] %}
    {% for result in results %}
        {% set node = result.node %}
        {% set response = result.adapter_response or {} %}
        {% do rows.append(
            "("
            ~ audit_sql_string(invocation_id) ~ ", "
            ~ audit_sql_string(flags.WHICH) ~ ", "
            ~ audit_sql_string(target.name) ~ ", "
            ~ audit_sql_string(dbt_version) ~ ", "
            ~ "'" ~ run_started_at.isoformat() ~ "'::timestamp_tz, "
            ~ audit_sql_string(node.unique_id) ~ ", "
            ~ audit_sql_string(node.name) ~ ", "
            ~ audit_sql_string(node.resource_type) ~ ", "
            ~ audit_sql_string(node.schema) ~ ", "
            ~ audit_sql_string(result.status) ~ ", "
            ~ audit_sql_number(result.execution_time) ~ ", "
            ~ audit_sql_number(response.get('rows_affected')) ~ ", "
            ~ audit_sql_number(result.failures) ~ ", "
            ~ audit_sql_string(response.get('query_id')) ~ ", "
            ~ audit_sql_string(result.message, 2000)
            ~ ")"
        ) %}
    {% endfor %}

    {% set insert_sql %}
        insert into {{ audit_relation }} (
            invocation_id, command, target_name, dbt_version, run_started_at,
            node_id, node_name, resource_type, schema_name, status,
            execution_time_s, rows_affected, failures, query_id, message
        )
        values
        {{ rows | join(',\n        ') }}
    {% endset %}
    {% do run_query(insert_sql) %}
    {{ log("Run log: " ~ rows | length ~ " rows written to " ~ audit_relation, info=True) }}

    {{ return('') }}
{% endmacro %}


{# Helpers: render a Python value as a safe Snowflake literal. #}
{% macro audit_sql_string(value, max_length=500) -%}
    {%- if value is none -%}
        null
    {%- else -%}
        '{{ (value | string)[:max_length] | replace("\\", "\\\\") | replace("'", "''") }}'
    {%- endif -%}
{%- endmacro %}

{% macro audit_sql_number(value) -%}
    {%- if value is none or (value | string) == '' -%}
        null
    {%- else -%}
        {{ value }}
    {%- endif -%}
{%- endmacro %}
