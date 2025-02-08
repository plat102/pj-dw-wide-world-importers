{{ config(schema='stg') }}

with raw as (
    select *
    from {{ source('wwi_raw', 'sales__OrderLines') }}
)

, raw__select_column as (
    select
        OrderLineID AS order_line_key
        , OrderID AS order_key
        , StockItemID AS stock_item_key
        , PackageTypeID AS package_type_key
        , Quantity AS quantity
        , UnitPrice AS unit_price
        , TaxRate AS tax_rate
        , PickedQuantity AS picked_quantity
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
