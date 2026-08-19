-- City with its state province and country flattened onto one row.
-- Extracted because dim_customer needs it twice, for the delivery and the postal address.

select
    stg_application_city.city_key
    , stg_application_city.city_name
    , stg_application_city.state_province_key
    , stg_application_state_province.state_province_name
    , stg_application_state_province.latest_recored_population as state_province_population
    , stg_application_state_province.country_key
    , stg_application_country.country_name
    , stg_application_country.country_formal_name
    , stg_application_country.country_type
    , stg_application_country.latest_recored_population as country_population
from {{ ref('stg_application_city') }}
left join {{ ref('stg_application_state_province') }}
    on stg_application_city.state_province_key = stg_application_state_province.state_province_key
left join {{ ref('stg_application_country') }}
    on stg_application_state_province.country_key = stg_application_country.country_key
