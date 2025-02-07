with raw as (
    select *
    from {{ source('wwi_raw', 'purchasing__Suppliers') }}
)
select
    SupplierID AS supplier_key
    , SupplierName AS supplier_name
    , SupplierCategoryID AS supplier_category_key
    , PostalCityID AS postal_city_key
from raw
