with raw as (
    select *
    from {{ source('wwi_raw', 'purchasing__suppliers') }}
)
select
    supplier_id as supplier_key
    , supplier_name
    , supplier_category_id as supplier_category_key
    , postal_city_id as postal_city_key
from raw
