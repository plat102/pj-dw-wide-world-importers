
with stg_city__flatten as (
    select 
        city_key
        , city_name
        , stg_application_city.state_province_key
        , stg_application_state_province.state_province_name
        , stg_application_state_province.latest_recored_population as state_province_population
        , stg_application_state_province.country_key
        , stg_application_country.country_name
        , stg_application_country.country_formal_name
        , stg_application_country.country_type
        , stg_application_country.latest_recored_population as country_population
    from {{ref('stg_application_city')}}
    left join {{ref('stg_application_state_province')}} on stg_application_city.state_province_key = stg_application_state_province.state_province_key
    left join {{ref('stg_application_country')}}on stg_application_state_province.country_key = stg_application_country.country_key
)

select 
    stg_sales_customer.customer_key AS customer_key
    , stg_sales_customer.customer_name AS customer_name
    , stg_sales_customer.bill_to_customer_key AS bill_to_customer_key
    -- , stg_sales_customer.customer_category_key AS customer_category_key
    , stg_sales_customer_category.customer_category_name AS customer_category_name
    , stg_sales_customer.buying_group_key AS buying_group_key
    , stg_sales_buying_group.buying_group_name AS buying_group_name
    -- , stg_sales_customer.primary_contact_person_key AS primary_contact_person_key
    , dim_person_primary.person_full_name AS primary_contact_full_name
    , dim_person_primary.is_system_user AS primary_contact_is_system_user
    , dim_person_primary.is_employee AS primary_contact_is_employee
    , dim_person_primary.is_salesperson AS primary_contact_is_salesperson
    , dim_person_primary.phone_number AS primary_contact_phone_number
    , dim_person_primary.email_address AS primary_contact_email_address
    -- , stg_sales_customer.alternate_contact_person_key AS alternate_contact_person_key
    , dim_person_alternate.person_full_name AS alternate_contact_full_name
    -- , stg_sales_customer.delivery_method_key AS delivery_method_key
    , stg_application_delivery_method.delivery_method_name AS delivery_method_name
    , stg_sales_customer.delivery_city_key
    , dim_city_delivery.city_name AS delivery_city_name
    , dim_city_delivery.state_province_name AS delivery_state_province_name
    , dim_city_delivery.state_province_population AS delivery_state_province_population
    , dim_city_delivery.country_name AS delivery_country_name
    , dim_city_delivery.country_formal_name AS delivery_country_formal_name
    , dim_city_delivery.country_type AS delivery_country_type
    , dim_city_delivery.country_population AS delivery_country_population
    , stg_sales_customer.postal_city_key
    , stg_sales_customer.credit_limit
    , stg_sales_customer.standard_discount_percentage
    , stg_sales_customer.is_on_credit_hold
    , stg_sales_customer.payment_term_days
    , stg_sales_customer.phone_number
    , stg_sales_customer.website_url 
    , stg_sales_customer.delivery_address_line_1
    , stg_sales_customer.delivery_address_line_2
    , stg_sales_customer.delivery_postal_code
    , stg_sales_customer.delivery_location
    , stg_sales_customer.postal_address_line_1
    , stg_sales_customer.postal_address_line_2
    , stg_sales_customer.postal_postal_code
from {{ref('stg_sales_customer')}}
left join {{ref('stg_sales_customer_category')}}
    on stg_sales_customer.customer_category_key = stg_sales_customer_category.customer_category_key
left join {{ref('stg_sales_buying_group')}}
    on stg_sales_customer.buying_group_key = stg_sales_buying_group.buying_group_key
left join {{ref('stg_application_person')}} as dim_person_primary
    on stg_sales_customer.primary_contact_person_key = dim_person_primary.person_key
left join {{ref('stg_application_person')}} as dim_person_alternate
    on stg_sales_customer.alternate_contact_person_key = dim_person_alternate.person_key
left join {{ref('stg_application_delivery_method')}}
    on stg_sales_customer.delivery_method_key = stg_application_delivery_method.delivery_method_key
left join stg_city__flatten as dim_city_delivery
    on stg_sales_customer.delivery_city_key = dim_city_delivery.city_key
left join stg_city__flatten as dim_city_postal
    on stg_sales_customer.postal_city_key = dim_city_postal.city_key

