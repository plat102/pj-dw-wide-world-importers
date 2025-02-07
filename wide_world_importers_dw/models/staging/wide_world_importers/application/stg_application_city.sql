with raw as (
    select *
    from {{ source('wwi_raw', 'application__Cities') }}
)
select
    CityID AS city_key
    , CityName AS city_name
    , StateProvinceID AS state_province_key
    , Location AS location_key
from raw
