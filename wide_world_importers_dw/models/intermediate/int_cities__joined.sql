-- City with its state province and country on one row. One consumer today, dim_customer's
-- delivery city; postal city becomes the second the day the two city keys diverge.

select
    stg_application__cities.city_key
    , stg_application__cities.city_name
    , stg_application__cities.state_province_key
    , stg_application__state_provinces.state_province_name
    , stg_application__state_provinces.latest_recored_population as state_province_population
    , stg_application__state_provinces.country_key
    , stg_application__countries.country_name
    , stg_application__countries.country_formal_name
    , stg_application__countries.country_type
    , stg_application__countries.latest_recored_population as country_population
from {{ ref('stg_application__cities') }}
left join {{ ref('stg_application__state_provinces') }}
    on stg_application__cities.state_province_key = stg_application__state_provinces.state_province_key
left join {{ ref('stg_application__countries') }}
    on stg_application__state_provinces.country_key = stg_application__countries.country_key
