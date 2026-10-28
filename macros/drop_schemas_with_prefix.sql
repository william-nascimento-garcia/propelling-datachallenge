{#
    Housekeeping for CI: drops every schema created by one pull request.

    Usage:
        dbt run-operation drop_schemas_with_prefix --args "{prefix: CI_PR_12}"

    Safety: only prefixes starting with CI_ or DEV_ are accepted, and the match
    is an exact "starts with <prefix>_" check done in Jinja (not LIKE, where "_"
    is a wildcard and CI_PR_1 would also match CI_PR_12).
#}
{% macro drop_schemas_with_prefix(prefix) %}
    {% set prefix = prefix | upper %}
    {% if not (prefix.startswith('CI_') or prefix.startswith('DEV_')) %}
        {{ exceptions.raise_compiler_error("Refusing to drop schemas for prefix '" ~ prefix ~ "'. Only CI_* or DEV_* are allowed.") }}
    {% endif %}

    {% set list_sql %}
        select schema_name
        from {{ target.database }}.information_schema.schemata
        where schema_name not in ('INFORMATION_SCHEMA', 'PUBLIC')
    {% endset %}

    {% if execute %}
        {% set schemas = run_query(list_sql).columns[0].values() %}
        {% for schema in schemas %}
            {% if schema == prefix or schema.startswith(prefix ~ '_') %}
                {% do run_query('drop schema if exists ' ~ target.database ~ '.' ~ schema ~ ' cascade') %}
                {{ log('Dropped schema ' ~ target.database ~ '.' ~ schema, info=True) }}
            {% endif %}
        {% endfor %}
    {% endif %}
{% endmacro %}
