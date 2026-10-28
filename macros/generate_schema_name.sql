{#
    Override of dbt's default schema naming.

    Default dbt behaviour concatenates <target_schema>_<custom_schema> in every
    environment, which would give e.g. PUBLIC_BRONZE in production.

    Here:
      * prod      -> BRONZE / SILVER / GOLD (exact names, as required)
      * dev / ci  -> <target_schema>_BRONZE ... (isolated sandbox per developer / PR)
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema | upper }}
    {%- elif target.name == 'prod' -%}
        {{ custom_schema_name | trim | upper }}
    {%- else -%}
        {{ target.schema | upper }}_{{ custom_schema_name | trim | upper }}
    {%- endif -%}
{%- endmacro %}
