-- Declared, not inferred: a cold parse sometimes scheduled this test ahead of the model it reads.
-- depends_on: {{ ref('dim_date') }}

-- Pins dim_date where its arithmetic is easiest to get wrong. One row per disagreement.

with expected (full_date, fiscal_year, fiscal_qtr, year_week, week_day, day_is_weekday) as (
    values
        -- Wide World Importers' fiscal year starts on 1 November (see fiscal_year_start_month in
        -- dbt_project.yml), so October closes FY2024 and November opens FY2025.
        (date '2024-10-31', 2024, 'Q4', 202444, 5, 1),
        (date '2024-11-01', 2025, 'Q1', 202444, 6, 1),
        -- ISO week 1 of 2025 begins while the calendar still says December.
        (date '2024-12-30', 2025, 'Q1', 202501, 2, 1),
        -- Saturday, Sunday, Monday: the weekend flag and the 1=Sunday numbering.
        (date '2025-01-04', 2025, 'Q1', 202501, 7, 0),
        (date '2025-01-05', 2025, 'Q1', 202501, 1, 0),
        (date '2025-01-06', 2025, 'Q1', 202502, 2, 1),
        -- Last day of fiscal Q1 and first of fiscal Q2.
        (date '2025-01-31', 2025, 'Q1', 202505, 6, 1),
        (date '2025-02-01', 2025, 'Q2', 202505, 7, 0)
)

select
    e.full_date,
    e.fiscal_year     as expected_fiscal_year,     d.fiscal_year     as actual_fiscal_year,
    e.fiscal_qtr      as expected_fiscal_qtr,      d.fiscal_qtr      as actual_fiscal_qtr,
    e.year_week       as expected_year_week,       d.year_week       as actual_year_week,
    e.week_day        as expected_week_day,        d.week_day        as actual_week_day,
    e.day_is_weekday  as expected_day_is_weekday,  d.day_is_weekday  as actual_day_is_weekday
from expected e
-- `.render()`: dim_date is generated, not read from raw, so `make build_empty` builds all of it,
-- and this test must read all of it too rather than the zero rows `--empty` gives every ref.
left join {{ ref('dim_date').render() }} d on d.full_date = e.full_date
where d.full_date is null
   or d.fiscal_year    is distinct from e.fiscal_year
   or d.fiscal_qtr     is distinct from e.fiscal_qtr
   or d.year_week      is distinct from e.year_week
   or d.week_day       is distinct from e.week_day
   or d.day_is_weekday is distinct from e.day_is_weekday
