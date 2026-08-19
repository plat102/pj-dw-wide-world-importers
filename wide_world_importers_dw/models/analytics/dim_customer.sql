-- Natural keys of joined-in dimensions are dropped on purpose: the attribute is carried
-- here, so the key would only invite a second join downstream.

select
    stg_sales_customer.customer_key
    , stg_sales_customer.customer_name
    , stg_sales_customer.bill_to_customer_key
    , stg_sales_customer_category.customer_category_name
    , stg_sales_customer.buying_group_key
    , stg_sales_buying_group.buying_group_name
    , person_primary.person_full_name as primary_contact_full_name
    , person_primary.is_system_user as primary_contact_is_system_user
    , person_primary.is_employee as primary_contact_is_employee
    , person_primary.is_salesperson as primary_contact_is_salesperson
    , person_primary.phone_number as primary_contact_phone_number
    , person_primary.email_address as primary_contact_email_address
    , person_alternate.person_full_name as alternate_contact_full_name
    , stg_application_delivery_method.delivery_method_name
    , stg_sales_customer.delivery_city_key
    , city_delivery.city_name as delivery_city_name
    , city_delivery.state_province_name as delivery_state_province_name
    , city_delivery.state_province_population as delivery_state_province_population
    , city_delivery.country_name as delivery_country_name
    , city_delivery.country_formal_name as delivery_country_formal_name
    , city_delivery.country_type as delivery_country_type
    , city_delivery.country_population as delivery_country_population
    , stg_sales_customer.postal_city_key
    , stg_sales_customer.credit_limit
    , stg_sales_customer.standard_discount_percentage
    , stg_sales_customer.is_on_credit_hold
    , stg_sales_customer.payment_term_days
    , stg_sales_customer.phone_number
    , stg_sales_customer.website_url
    , concat(stg_sales_customer.delivery_address_line_1, ' ', stg_sales_customer.delivery_address_line_2) as delivery_address
    , stg_sales_customer.delivery_postal_code
    , concat(stg_sales_customer.postal_address_line_1, ' ', stg_sales_customer.postal_address_line_2) as postal_address
    , stg_sales_customer.postal_postal_code
from {{ ref('stg_sales_customer') }}
left join {{ ref('stg_sales_customer_category') }}
    on stg_sales_customer.customer_category_key = stg_sales_customer_category.customer_category_key
left join {{ ref('stg_sales_buying_group') }}
    on stg_sales_customer.buying_group_key = stg_sales_buying_group.buying_group_key
left join {{ ref('stg_application_person') }} as person_primary
    on stg_sales_customer.primary_contact_person_key = person_primary.person_key
left join {{ ref('stg_application_person') }} as person_alternate
    on stg_sales_customer.alternate_contact_person_key = person_alternate.person_key
left join {{ ref('stg_application_delivery_method') }}
    on stg_sales_customer.delivery_method_key = stg_application_delivery_method.delivery_method_key
left join {{ ref('int_city_flattened') }} as city_delivery
    on stg_sales_customer.delivery_city_key = city_delivery.state_province_key
