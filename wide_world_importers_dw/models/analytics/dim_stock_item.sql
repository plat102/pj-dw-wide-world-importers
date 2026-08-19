-- The surrogate key is here so SCD Type 2 can later give one stock item several rows.
-- Its original justification was versioning UnitPrice, and that turned out to be false: no item
-- in the source has ever had more than one distinct price, and the data generator never writes
-- to that table at all. The key stays because it costs nothing and nothing else depends on it --
-- not because this source has history to track. When SCD2 lands, the valid-from timestamp joins
-- the hash; today the natural key is the whole input.

select
    {{ dbt_utils.generate_surrogate_key(['stg_warehouse_stock_item.stock_item_key']) }} as stock_item_sk
    , stg_warehouse_stock_item.stock_item_key
    , stg_warehouse_stock_item.stock_item_name
    , stg_warehouse_stock_item.supplier_key
    , stg_warehouse_stock_item.color_key
    , package_type_unit.package_type_name as unit_package_type_name
    , package_type_outer.package_type_name as outer_package_type_name
    , stg_warehouse_stock_item.brand
    , stg_warehouse_stock_item.size
    , stg_warehouse_stock_item.lead_time_days
    , stg_warehouse_stock_item.quantity_per_outer
    , stg_warehouse_stock_item.is_chiller_stock
    , stg_warehouse_stock_item.tax_rate
    , stg_warehouse_stock_item.unit_price
    , stg_warehouse_stock_item.recommended_retail_price
    , stg_warehouse_stock_item.typical_weight_per_unit
    , stg_warehouse_color.color_name
    , stg_purchasing_supplier.supplier_name
from {{ ref('stg_warehouse_stock_item') }}
left join {{ ref('stg_warehouse_package_type') }} as package_type_unit
    on stg_warehouse_stock_item.unit_package_type_key = package_type_unit.package_type_key
left join {{ ref('stg_warehouse_package_type') }} as package_type_outer
    on stg_warehouse_stock_item.outer_package_type_key = package_type_outer.package_type_key
left join {{ ref('stg_warehouse_color') }}
    on stg_warehouse_stock_item.color_key = stg_warehouse_color.color_key
left join {{ ref('stg_purchasing_supplier') }}
    on stg_warehouse_stock_item.supplier_key = stg_purchasing_supplier.supplier_key
