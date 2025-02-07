{{ 
    config(
        materialized='table'
    )
}}

with date_array as (
    select
        full_date
    from
        unnest(generate_date_array(date '2000-01-01', date '2050-12-31', interval 1 day)) as full_date
)

select
    format_date('%Y%m%d', full_date) as date_key,
    full_date,
    extract(year from full_date) as year,
    extract(year from full_date) * 100 + extract(week from full_date) as year_week,
    extract(year from full_date) * 1000 + extract(dayofyear from full_date) as year_day,
    case 
        when extract(month from full_date) >= 4 then extract(year from full_date) + 1
        else extract(year from full_date)
    end as fiscal_year,
    concat('Q', cast(div(extract(month from full_date) - 1, 3) + 1 as string)) as fiscal_qtr,
    extract(month from full_date) as month,
    format_date('%B', full_date) as month_name,
    extract(dayofweek from full_date) as week_day,
    format_date('%A', full_date) as day_name,
    case when extract(dayofweek from full_date) in (1, 7) then 0 else 1 end as day_is_weekday
from
    date_array
