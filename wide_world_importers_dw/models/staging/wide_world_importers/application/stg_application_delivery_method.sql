with raw as (
    select *
    from {{ source('wwi_raw', 'application__delivery_methods') }}
)
select 
    delivery_method_id AS delivery_method_key
    , delivery_method_name AS delivery_method_name
from raw
