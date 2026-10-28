{#
    Custom generic test: chronological consistency between two columns of the
    same row, e.g. a receipt can never happen before the shipment.

    Usage:
        - name: receipt_date
          data_tests:
            - not_before: {column: ship_date}
#}
{% test not_before(model, column_name, column) %}

select
    {{ column_name }} as later_value,
    {{ column }}      as earlier_value
from {{ model }}
where {{ column_name }} < {{ column }}

{% endtest %}
