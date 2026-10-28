-- Calendar dimension. Role-playing: the fact joins it as order, ship,
-- commit and receipt date. Built with Snowflake's GENERATOR (no source table
-- needed); the range comes from the dim_date_start / dim_date_end vars.

-- Columns dropped: none. dim_date has no source table: it is generated with GENERATOR,
-- so every column here is created, not selected from an upstream model.

{%- set start_date = modules.datetime.date.fromisoformat(var('dim_date_start')) -%}
{%- set end_date = modules.datetime.date.fromisoformat(var('dim_date_end')) -%}
{%- set day_count = (end_date - start_date).days + 1 %}

with calendar as (
    select
        dateadd(
            day,
            row_number() over (order by seq4()) - 1,
            '{{ start_date }}'::date
        )::date as date_day
    from table(generator(rowcount => {{ day_count }}))
)

select
    to_char(date_day, 'YYYYMMDD')::varchar                   as date_key,
    date_day::date                                           as date_day,
    year(date_day)::number(38, 0)                            as year_number,
    quarter(date_day)::number(38, 0)                         as quarter_number,
    (year(date_day) || '-Q' || quarter(date_day))::varchar   as year_quarter,
    month(date_day)::number(38, 0)                           as month_number,
    monthname(date_day)::varchar                             as month_name,
    to_char(date_day, 'YYYY-MM')::varchar                    as year_month,
    date_trunc('month', date_day)::date                      as month_start_date,
    weekiso(date_day)::number(38, 0)                         as iso_week_number,
    dayofweekiso(date_day)::number(38, 0)                    as day_of_week_number,
    dayname(date_day)::varchar                               as day_name,
    (dayofweekiso(date_day) in (6, 7))::boolean              as is_weekend
from calendar
