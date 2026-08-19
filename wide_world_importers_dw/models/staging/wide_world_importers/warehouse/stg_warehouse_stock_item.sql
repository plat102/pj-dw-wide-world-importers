with raw as (
    select *
    from {{ source('wwi_raw', 'warehouse__stock_items') }}
)
select
    stock_item_id AS stock_item_key
    , stock_item_name AS stock_item_name
    , supplier_id AS supplier_key
    , color_id AS color_key
    , unit_package_id AS unit_package_type_key
    , outer_package_id AS outer_package_type_key
    , brand AS brand
    , size AS size
    , lead_time_days AS lead_time_days
    , quantity_per_outer
    , is_chiller_stock AS is_chiller_stock
    , tax_rate AS tax_rate
    , unit_price AS unit_price
    , recommended_retail_price AS recommended_retail_price
    , typical_weight_per_unit AS typical_weight_per_unit
from raw
