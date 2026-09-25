-- A joined-in dimension's natural key is dropped once its attributes are here. The keys that stay
-- are a self-reference the fact uses, or address a table with no dimension of its own.

select
    stg_sales__customers.customer_key
    , stg_sales__customers.customer_name
    , stg_sales__customers.bill_to_customer_key
    , stg_sales__customer_categories.customer_category_name
    , stg_sales__customers.buying_group_key
    , stg_sales__buying_groups.buying_group_name
    , person_primary.person_full_name as primary_contact_full_name
    , person_primary.is_system_user as primary_contact_is_system_user
    , person_primary.is_employee as primary_contact_is_employee
    , person_primary.is_salesperson as primary_contact_is_salesperson
    , person_primary.phone_number as primary_contact_phone_number
    , person_primary.email_address as primary_contact_email_address
    , person_alternate.person_full_name as alternate_contact_full_name
    , stg_application__delivery_methods.delivery_method_name
    , stg_sales__customers.delivery_city_key
    , city_delivery.city_name as delivery_city_name
    , city_delivery.state_province_name as delivery_state_province_name
    , city_delivery.state_province_population as delivery_state_province_population
    , city_delivery.country_name as delivery_country_name
    , city_delivery.country_formal_name as delivery_country_formal_name
    , city_delivery.country_type as delivery_country_type
    , city_delivery.country_population as delivery_country_population
    , stg_sales__customers.postal_city_key
    , stg_sales__customers.credit_limit
    , stg_sales__customers.standard_discount_percentage
    , stg_sales__customers.is_on_credit_hold
    , stg_sales__customers.payment_term_days
    , stg_sales__customers.phone_number
    , stg_sales__customers.website_url
    -- concat_ws, not concat: DuckDB's concat skips a NULL but keeps the separator, so a missing
    -- second line left a trailing space. No row needs it today; this is the guard.
    , nullif(trim(concat_ws(' ', stg_sales__customers.delivery_address_line_1, stg_sales__customers.delivery_address_line_2)), '') as delivery_address
    , stg_sales__customers.delivery_postal_code
    , nullif(trim(concat_ws(' ', stg_sales__customers.postal_address_line_1, stg_sales__customers.postal_address_line_2)), '') as postal_address
    , stg_sales__customers.postal_postal_code
from {{ ref('stg_sales__customers') }}
left join {{ ref('stg_sales__customer_categories') }}
    on stg_sales__customers.customer_category_key = stg_sales__customer_categories.customer_category_key
left join {{ ref('stg_sales__buying_groups') }}
    on stg_sales__customers.buying_group_key = stg_sales__buying_groups.buying_group_key
left join {{ ref('stg_application__people') }} as person_primary
    on stg_sales__customers.primary_contact_person_key = person_primary.person_key
left join {{ ref('stg_application__people') }} as person_alternate
    on stg_sales__customers.alternate_contact_person_key = person_alternate.person_key
left join {{ ref('stg_application__delivery_methods') }}
    on stg_sales__customers.delivery_method_key = stg_application__delivery_methods.delivery_method_key
left join {{ ref('int_cities__joined') }} as city_delivery
    on stg_sales__customers.delivery_city_key = city_delivery.city_key
