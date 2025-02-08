{{ config(schema='stg') }}

with raw as (
    select *
    from {{ source('wwi_raw', 'sales__Orders') }}
)

, raw__select_column as (
    select
        OrderID AS order_key
        , CustomerID AS customer_key
        , SalespersonPersonID AS salesperson_key
        , PickedByPersonID AS picked_by_person_key
        , ContactPersonID AS contact_person_key
        , BackorderOrderID AS backorder_order_key
        , OrderDate AS order_date_key
        , ExpectedDeliveryDate AS expected_delivery_date_key
        , IsUndersupplyBackordered AS is_undersupply_backordered
        , PickingCompletedWhen AS picking_completed_date_key
    from raw
)

, raw__add_cursor_timestamp as (
    select 
        *
        , current_timestamp() as processed_at
    from raw__select_column
    -- cursor timestamp should be loaded time of the data into data lake
    -- this is just a workaround
)

select * from raw__add_cursor_timestamp
