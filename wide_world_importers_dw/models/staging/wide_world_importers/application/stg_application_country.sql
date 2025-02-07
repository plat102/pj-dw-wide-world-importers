with raw as (
    select *
    from {{ source('wwi_raw', 'application__Countries') }}
)
select
    CountryID AS country_key
    , CountryName AS country_name
    , FormalName AS country_formal_name
    , CountryType AS country_type
    , LatestRecordedPopulation AS latest_recored_population
from raw
