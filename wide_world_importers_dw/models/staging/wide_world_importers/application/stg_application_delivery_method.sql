with raw as (
    select *
    from {{ source('wwi_raw', 'application__DeliveryMethods') }}
)
select 
    DeliveryMethodID AS delivery_method_key
    , DeliveryMethodName AS delivery_method_name
from raw
