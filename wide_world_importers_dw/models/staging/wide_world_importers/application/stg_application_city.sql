with raw as (
    select *
    from {{ source('wwi_raw', 'application__cities') }}
)
select
    city_id AS city_key
    , city_name AS city_name
    , state_province_id AS state_province_key
from raw
