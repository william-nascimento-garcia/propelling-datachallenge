{#
    Custom generic test: the column must be > 0 (or >= 0 with allow_zero=true).
    Nulls are ignored here on purpose; combine with not_null when needed.

    Usage:
        - name: quantity
          data_tests:
            - is_positive
            - is_positive: {allow_zero: true}
#}
{% test is_positive(model, column_name, allow_zero=false) %}

select {{ column_name }} as failing_value
from {{ model }}
where {{ column_name }} is not null
  and {{ column_name }} {{ '<' if allow_zero else '<=' }} 0

{% endtest %}
