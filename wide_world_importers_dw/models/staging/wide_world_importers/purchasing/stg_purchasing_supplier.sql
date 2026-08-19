with raw as (
    select *
    from {{ source('wwi_raw', 'purchasing__suppliers') }}
)
select
    supplier_id AS supplier_key
    , supplier_name AS supplier_name
    , supplier_category_id AS supplier_category_key
    , postal_city_id AS postal_city_key
from raw
