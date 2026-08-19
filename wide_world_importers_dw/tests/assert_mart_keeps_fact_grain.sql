-- Declared, not inferred: a cold parse intermittently failed to infer these and scheduled the
-- test ahead of the models it reads.
-- depends_on: {{ ref('fact_sales_order_line') }}
-- depends_on: {{ ref('mart_sales_order_line') }}

-- The mart joins ten dimensions onto the fact, each on a key unique in its dimension, so it must
-- come out at exactly the fact's row count. A duplicate key silently multiplies rows.

with counts as (
    select
        (select count(*) from {{ ref('fact_sales_order_line') }}) as fact_rows,
        (select count(*) from {{ ref('mart_sales_order_line') }}) as mart_rows
)

select fact_rows, mart_rows, mart_rows - fact_rows as extra_rows
from counts
where fact_rows <> mart_rows
