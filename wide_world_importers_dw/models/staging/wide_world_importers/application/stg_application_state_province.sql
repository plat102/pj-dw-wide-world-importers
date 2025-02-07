with raw as (
    select *
    from {{ source('wwi_raw', 'application__StateProvinces') }}
)
select
    StateProvinceID AS state_province_key
    , StateProvinceCode AS state_province_code
    , StateProvinceName AS state_province_name
    , CountryID AS country_key
    , LatestRecordedPopulation AS latest_recored_population
from raw
