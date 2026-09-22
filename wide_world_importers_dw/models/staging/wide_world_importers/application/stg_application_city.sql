with raw as (
    select *
    from {{ source('wwi_raw', 'application__cities') }}
)
select
    city_id as city_key
    , city_name
    , state_province_id as state_province_key
from raw
