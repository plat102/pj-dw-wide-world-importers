with raw as (
    select *
    from {{ source('wwi_raw', 'warehouse__package_types') }}
)
select
    package_type_id AS package_type_key
    , package_type_name AS package_type_name
from raw
