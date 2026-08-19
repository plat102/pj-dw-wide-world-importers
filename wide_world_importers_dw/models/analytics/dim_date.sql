{{
    config(
        materialized='table'
    )
}}

with date_array as (
    select
        cast(unnest(generate_series(date '2000-01-01', date '2050-12-31', interval 1 day)) as date) as full_date
)

select
    strftime(full_date, '%Y%m%d') as date_key,
    full_date,
    extract(year from full_date) as year,
    extract(isoyear from full_date) * 100 + extract(week from full_date) as year_week,
    extract(year from full_date) * 1000 + extract(dayofyear from full_date) as year_day,
    case
        when extract(month from full_date) >= 4 then extract(year from full_date) + 1
        else extract(year from full_date)
    end as fiscal_year,
    concat('Q', cast(((extract(month from full_date) - 4 + 12) % 12) // 3 + 1 as varchar)) as fiscal_qtr,
    extract(month from full_date) as month,
    strftime(full_date, '%B') as month_name,
    extract(dayofweek from full_date) + 1 as week_day,
    strftime(full_date, '%A') as day_name,
    case when extract(dayofweek from full_date) + 1 in (1, 7) then 0 else 1 end as day_is_weekday
from
    date_array
