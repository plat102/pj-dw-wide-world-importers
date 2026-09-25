with raw as (
    select *
    from {{ source('wwi_raw', 'warehouse__colors') }}
)
select
    color_id as color_key
    , color_name
from raw
