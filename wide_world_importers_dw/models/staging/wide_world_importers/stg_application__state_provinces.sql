with raw as (
    select *
    from {{ source('wwi_raw', 'application__state_provinces') }}
)
select
    state_province_id as state_province_key
    , state_province_code
    , state_province_name
    , country_id as country_key
    , latest_recorded_population as latest_recored_population
from raw
