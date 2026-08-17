with raw as (
    select *
    from {{ source('wwi_raw', 'sales__customer_categories') }}
)
select
    customer_category_id as customer_category_key
    , customer_category_name as customer_category_name
from raw
