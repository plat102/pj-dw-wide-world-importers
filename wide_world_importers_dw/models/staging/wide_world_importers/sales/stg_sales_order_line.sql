{{ config(schema='stg') }}

with raw as (
    select *
    from {{ source('wwi_raw', 'sales__order_lines') }}
)

, raw__select_column as (
    select
        order_line_id AS order_line_key
        , order_id AS order_key
        , stock_item_id AS stock_item_key
        , package_type_id AS package_type_key
        , quantity AS quantity
        , unit_price AS unit_price
        , tax_rate AS tax_rate
        , picked_quantity AS picked_quantity
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
