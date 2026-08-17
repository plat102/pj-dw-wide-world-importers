with raw as (
    select *
    from {{ source('wwi_raw', 'application__state_provinces') }}
)
select
    state_province_id AS state_province_key
    , state_province_code AS state_province_code
    , state_province_name AS state_province_name
    , country_id AS country_key
    , latest_recorded_population AS latest_recored_population
from raw
