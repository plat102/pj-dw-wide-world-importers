with raw as (
    select *
    from {{ source('wwi_raw', 'warehouse__colors') }}
)
select
    color_id AS color_key
    , color_name AS color_name
from raw
