with raw as (
    select *
    from {{ source('wwi_raw', 'purchasing__SupplierCategories') }}
)
select
    SupplierCategoryID AS supplier_category_key
    , SupplierCategoryName AS supplier_category_name
from raw
