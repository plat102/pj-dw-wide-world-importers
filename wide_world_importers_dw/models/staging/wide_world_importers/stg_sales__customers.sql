with raw as (
    select *
    from {{ source('wwi_raw', 'sales__customers') }}
)
select
    customer_id as customer_key
    , customer_name
    , bill_to_customer_id as bill_to_customer_key
    , customer_category_id as customer_category_key
    , buying_group_id as buying_group_key
    , primary_contact_person_id as primary_contact_person_key
    , alternate_contact_person_id as alternate_contact_person_key
    , delivery_method_id as delivery_method_key
    , delivery_city_id as delivery_city_key
    , postal_city_id as postal_city_key
    , credit_limit
    , standard_discount_percentage
    , is_on_credit_hold
    , payment_days as payment_term_days
    , phone_number
    , website_url
    , delivery_address_line1 as delivery_address_line_1
    , delivery_address_line2 as delivery_address_line_2
    , delivery_postal_code
    , postal_address_line1 as postal_address_line_1
    , postal_address_line2 as postal_address_line_2
    , postal_postal_code
    , {{ processed_at() }} as processed_at
from raw
