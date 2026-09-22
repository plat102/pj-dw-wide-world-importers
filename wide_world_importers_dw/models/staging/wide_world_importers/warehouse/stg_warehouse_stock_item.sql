with raw as (
    select *
    from {{ source('wwi_raw', 'warehouse__stock_items') }}
)
select
    stock_item_id as stock_item_key
    , stock_item_name
    , supplier_id as supplier_key
    , color_id as color_key
    , unit_package_id as unit_package_type_key
    , outer_package_id as outer_package_type_key
    , brand
    , size
    , lead_time_days
    , quantity_per_outer
    , is_chiller_stock
    , tax_rate
    , unit_price
    , recommended_retail_price
    , typical_weight_per_unit
from raw
