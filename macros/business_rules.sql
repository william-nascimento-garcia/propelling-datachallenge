{#
    Single definition of the core revenue rules, used by Silver.
    If the business changes how "net revenue" is calculated, it changes here once.
#}

{# Net revenue of a line: extended price after discount, before tax. #}
{% macro net_amount(extended_price, discount) -%}
    round({{ extended_price }} * (1 - {{ discount }}), 2)
{%- endmacro %}

{# Amount actually invoiced to the customer: net revenue plus tax. #}
{% macro gross_amount_with_tax(extended_price, discount, tax) -%}
    round({{ extended_price }} * (1 - {{ discount }}) * (1 + {{ tax }}), 2)
{%- endmacro %}

{# Turns an UPPER CASE source label into a readable one ('UNITED STATES' -> 'United States'). #}
{% macro clean_label(column) -%}
    initcap(trim({{ column }}))
{%- endmacro %}
