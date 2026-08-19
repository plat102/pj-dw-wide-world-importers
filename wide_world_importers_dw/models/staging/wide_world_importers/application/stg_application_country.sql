with raw as (
    select *
    from {{ source('wwi_raw', 'application__countries') }}
)
select
    country_id AS country_key
    , country_name AS country_name
    , formal_name AS country_formal_name
    , country_type AS country_type
    , latest_recorded_population AS latest_recored_population
from raw
