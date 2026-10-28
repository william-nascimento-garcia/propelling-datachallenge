{#
    Custom generic test: reconciliation between layers.
    The total of a measure must be identical in this model and in the model it
    was derived from (within a tolerance), proving no rows were lost or
    duplicated by joins.

    Usage (on a model):
        data_tests:
          - sum_matches:
              column: net_amount
              compare_model: ref('slv_lineitem')
              compare_column: net_amount
#}
{% test sum_matches(model, column, compare_model, compare_column=none, tolerance=0.01) %}

{% set compare_column = compare_column or column %}

with this_model as (
    select coalesce(sum({{ column }}), 0) as total from {{ model }}
),
other_model as (
    select coalesce(sum({{ compare_column }}), 0) as total from {{ compare_model }}
)
select
    this_model.total  as model_total,
    other_model.total as compare_total
from this_model
cross join other_model
where abs(this_model.total - other_model.total) > {{ tolerance }}

{% endtest %}
