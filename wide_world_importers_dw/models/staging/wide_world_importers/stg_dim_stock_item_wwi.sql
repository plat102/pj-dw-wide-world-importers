
select
    stg_warehouse_stock_item.stock_item_key
    , stg_warehouse_stock_item.stock_item_name
    , stg_warehouse_stock_item.supplier_key
    , stg_warehouse_stock_item.color_key
    -- , stg_warehouse_stock_item.unit_package_type_key AS unit_package_type_key
    , dim_package_type_unit.package_type_name AS unit_package_type_name
    -- , stg_warehouse_stock_item.outer_package_type_key AS outer_package_type_key
    , dim_package_type_outer.package_type_name AS outer_package_type_name
    , stg_warehouse_stock_item.brand
    , stg_warehouse_stock_item.size
    , stg_warehouse_stock_item.lead_time_days
    , stg_warehouse_stock_item.quantiy_per_outer
    , stg_warehouse_stock_item.is_chiller_stock
    , stg_warehouse_stock_item.tax_rate
    , stg_warehouse_stock_item.unit_price
    , stg_warehouse_stock_item.recommended_retail_price
    , stg_warehouse_stock_item.typical_weight_per_unit
    , stg_warehouse_color.color_name
    , stg_purchasing_supplier.supplier_name
from {{ ref('stg_warehouse_stock_item') }} 
    left join {{ ref('stg_warehouse_package_type') }} as dim_package_type_unit
        on stg_warehouse_stock_item.unit_package_type_key = dim_package_type_unit.package_type_key
    left join {{ ref('stg_warehouse_package_type') }} as dim_package_type_outer
        on stg_warehouse_stock_item.outer_package_type_key = dim_package_type_outer.package_type_key
    left join {{ ref('stg_warehouse_color') }}
        on stg_warehouse_stock_item.color_key = stg_warehouse_color.color_key
    left join {{ ref('stg_purchasing_supplier') }}
        on stg_warehouse_stock_item.supplier_key = stg_purchasing_supplier.supplier_key
