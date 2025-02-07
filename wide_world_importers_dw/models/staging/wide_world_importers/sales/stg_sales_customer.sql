{{ config(schema='stg') }}

with raw as (
    select *
    from {{ source('wwi_raw', 'sales__Customers') }}
)

, raw__select_column as (
    select
        CustomerID AS customer_key
        , CustomerName AS customer_name
        , BillToCustomerID AS bill_to_customer_key
        , CustomerCategoryID AS customer_category_key
        , BuyingGroupID AS buying_group_key
        , PrimaryContactPersonID AS primary_contact_person_key
        , AlternateContactPersonID AS alternate_contact_person_key
        , DeliveryMethodID AS delivery_method_key
        , DeliveryCityID AS delivery_city_key
        , PostalCityID AS postal_city_key
        , CreditLimit AS credit_limit
        , StandardDiscountPercentage AS standard_discount_percentage
        , IsOnCreditHold AS is_on_credit_hold
        , PaymentDays AS payment_term_days
        , PhoneNumber AS phone_number
        , WebsiteURL AS website_url
        , DeliveryAddressLine1 AS delivery_address_line_1
        , DeliveryAddressLine2 AS delivery_address_line_2
        , DeliveryPostalCode AS delivery_postal_code
        , DeliveryLocation AS delivery_location
        , PostalAddressLine1 AS postal_address_line_1
        , PostalAddressLine2 AS postal_address_line_2
        , PostalPostalCode AS postal_postal_code 
    from raw
)

, raw__add_cursor_timestamp as (
    select 
        *
        , current_timestamp() as processed_at
    from raw__select_column
    -- cursor timestamp should be loaded time of the data into data lake
    -- this is just a workaround
)

select * from raw__add_cursor_timestamp
