-- Declared, not inferred: a cold parse sometimes scheduled this test ahead of the models it reads.
-- depends_on: {{ ref('fct_sales_order_line') }}
-- depends_on: {{ ref('obt_sales_order_line') }}

-- Every dimension is joined on a key unique in it, so the mart must come out at the fact's row
-- count. A duplicate key silently multiplies rows.

with counts as (
    select
        (select count(*) from {{ ref('fct_sales_order_line') }}) as fact_rows,
        (select count(*) from {{ ref('obt_sales_order_line') }}) as mart_rows
)

select fact_rows, mart_rows, mart_rows - fact_rows as extra_rows
from counts
where fact_rows <> mart_rows
