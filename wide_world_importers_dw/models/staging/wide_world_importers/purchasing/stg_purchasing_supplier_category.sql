with raw as (
    select *
    from {{ source('wwi_raw', 'purchasing__supplier_categories') }}
)
select
    supplier_category_id AS supplier_category_key
    , supplier_category_name AS supplier_category_name
from raw
