with raw as (
    select *
    from {{ source('wwi_raw', 'warehouse__StockItems') }}
)
select
    StockItemID AS stock_item_key
    , StockItemName AS stock_item_name
    , SupplierID AS supplier_key
    , ColorID AS color_key
    , UnitPackageID AS unit_package_type_key
    , OuterPackageID AS outer_package_type_key
    , Brand AS brand
    , Size AS size
    , LeadTimeDays AS lead_time_days
    , QuantityPerOuter AS quantiy_per_outer
    , IsChillerStock AS is_chiller_stock
    , TaxRate AS tax_rate
    , UnitPrice AS unit_price
    , RecommendedRetailPrice AS recommended_retail_price
    , TypicalWeightPerUnit AS typical_weight_per_unit
from raw
