{{ config(schema='stg') }}

with raw as (
    select *
    from {{ source('wwi_raw', 'sales__customers') }}
)

, raw__select_column as (
    select
        customer_id AS customer_key
        , customer_name AS customer_name
        , bill_to_customer_id AS bill_to_customer_key
        , customer_category_id AS customer_category_key
        , buying_group_id AS buying_group_key
        , primary_contact_person_id AS primary_contact_person_key
        , alternate_contact_person_id AS alternate_contact_person_key
        , delivery_method_id AS delivery_method_key
        , delivery_city_id AS delivery_city_key
        , postal_city_id AS postal_city_key
        , credit_limit AS credit_limit
        , standard_discount_percentage AS standard_discount_percentage
        , is_on_credit_hold AS is_on_credit_hold
        , payment_days AS payment_term_days
        , phone_number AS phone_number
        , website_url AS website_url
        , delivery_address_line1 AS delivery_address_line_1
        , delivery_address_line2 AS delivery_address_line_2
        , delivery_postal_code AS delivery_postal_code
        , postal_address_line1 AS postal_address_line_1
        , postal_address_line2 AS postal_address_line_2
        , postal_postal_code AS postal_postal_code 
    from raw
)

, raw__add_cursor_timestamp as (
    select 
        *
        , current_timestamp as processed_at
    from raw__select_column
    -- cursor timestamp should be loaded time of the data into data lake
    -- this is just a workaround
)

select * from raw__add_cursor_timestamp
