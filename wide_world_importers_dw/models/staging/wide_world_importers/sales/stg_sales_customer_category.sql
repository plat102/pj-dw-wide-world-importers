with raw as (
    select *
    from {{ source('wwi_raw', 'sales__CustomerCategories') }}
)
select
    CustomerCategoryID as customer_category_key
    , CustomerCategoryName as customer_category_name
from raw
