with raw as (
    select *
    from {{ source('wwi_raw', 'sales__order_lines') }}
)
select
    order_line_id as order_line_key
    , order_id as order_key
    , stock_item_id as stock_item_key
    , package_type_id as package_type_key
    , quantity
    , unit_price
    , tax_rate
    , picked_quantity
    , picking_completed_when as picking_completed_date_key
    , {{ snapshot_processed_at() }} as processed_at
from raw
