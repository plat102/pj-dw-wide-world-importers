with raw as (
    select *
    from {{ source('wwi_raw', 'application__countries') }}
)
select
    country_id as country_key
    , country_name
    , formal_name as country_formal_name
    , country_type
    , latest_recorded_population as latest_recored_population
from raw
