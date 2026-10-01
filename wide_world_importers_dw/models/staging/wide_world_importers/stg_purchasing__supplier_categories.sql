with raw as (
    select *
    from {{ source('wwi_raw', 'purchasing__supplier_categories') }}
)
select
    supplier_category_id as supplier_category_key
    , supplier_category_name
from raw
