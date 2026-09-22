with raw as (
    select *
    from {{ source('wwi_raw', 'application__people') }}
)
select
    person_id as person_key
    , full_name as person_full_name
    , preferred_name as person_preferred_name
    , is_system_user
    , is_employee
    , is_salesperson
    , phone_number
    , email_address
    , {{ snapshot_processed_at() }} as processed_at
from raw
