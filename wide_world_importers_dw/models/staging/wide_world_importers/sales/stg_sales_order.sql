{{ config(schema='stg') }}

with raw as (
    select *
    from {{ source('wwi_raw', 'sales__orders') }}
)

, raw__select_column as (
    select
        order_id AS order_key
        , customer_id AS customer_key
        , salesperson_person_id AS salesperson_key
        , picked_by_person_id AS picked_by_person_key
        , contact_person_id AS contact_person_key
        , backorder_order_id AS backorder_order_key
        , order_date AS order_date_key
        , expected_delivery_date AS expected_delivery_date_key
        , is_undersupply_backordered AS is_undersupply_backordered
        , picking_completed_when AS picking_completed_date_key
    from raw
)

, raw__add_cursor_timestamp as (
    select 
        *
        , current_timestamp as processed_at
    from raw__select_column
    -- cursor timestamp should be loaded time of the data into data lake
    -- this is just a workaround
)

select * from raw__add_cursor_timestamp
