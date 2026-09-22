with raw as (
    select *
    from {{ source('wwi_raw', 'sales__orders') }}
)
select
    order_id as order_key
    , customer_id as customer_key
    , salesperson_person_id as salesperson_key
    , picked_by_person_id as picked_by_person_key
    , contact_person_id as contact_person_key
    , backorder_order_id as backorder_order_key
    , order_date as order_date_key
    , expected_delivery_date as expected_delivery_date_key
    , is_undersupply_backordered
    , picking_completed_when as picking_completed_date_key
    , {{ snapshot_processed_at() }} as processed_at
from raw
