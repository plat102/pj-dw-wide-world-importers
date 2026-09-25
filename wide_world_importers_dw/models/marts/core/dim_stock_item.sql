-- Keyed on the natural key, like every other dimension. A surrogate key for a future SCD2 was
-- dropped: nothing joined it, and SCD2 means rewiring the star, not adding one column.

select
    stg_warehouse__stock_items.stock_item_key
    , stg_warehouse__stock_items.stock_item_name
    , stg_warehouse__stock_items.supplier_key
    , stg_warehouse__stock_items.color_key
    , package_type_unit.package_type_name as unit_package_type_name
    , package_type_outer.package_type_name as outer_package_type_name
    , stg_warehouse__stock_items.brand
    , stg_warehouse__stock_items.size
    , stg_warehouse__stock_items.lead_time_days
    , stg_warehouse__stock_items.quantity_per_outer
    , stg_warehouse__stock_items.is_chiller_stock
    , stg_warehouse__stock_items.tax_rate
    , stg_warehouse__stock_items.unit_price
    , stg_warehouse__stock_items.recommended_retail_price
    , stg_warehouse__stock_items.typical_weight_per_unit
    , stg_warehouse__colors.color_name
    , stg_purchasing__suppliers.supplier_name
from {{ ref('stg_warehouse__stock_items') }}
left join {{ ref('stg_warehouse__package_types') }} as package_type_unit
    on stg_warehouse__stock_items.unit_package_type_key = package_type_unit.package_type_key
left join {{ ref('stg_warehouse__package_types') }} as package_type_outer
    on stg_warehouse__stock_items.outer_package_type_key = package_type_outer.package_type_key
left join {{ ref('stg_warehouse__colors') }}
    on stg_warehouse__stock_items.color_key = stg_warehouse__colors.color_key
left join {{ ref('stg_purchasing__suppliers') }}
    on stg_warehouse__stock_items.supplier_key = stg_purchasing__suppliers.supplier_key
