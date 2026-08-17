-- The wide mart joins ten dimensions onto the fact. Every one of those joins is on a key
-- that must be unique in its dimension, so the mart has to come out at exactly the fact's
-- row count. A dimension that gains a duplicate key silently multiplies rows here, and a
-- row count is the only place that shows.

with counts as (
    select
        (select count(*) from {{ ref('fact_sales_order_line') }}) as fact_rows,
        (select count(*) from {{ ref('mart_sales_order_line') }}) as mart_rows
)

select fact_rows, mart_rows, mart_rows - fact_rows as extra_rows
from counts
where fact_rows <> mart_rows
