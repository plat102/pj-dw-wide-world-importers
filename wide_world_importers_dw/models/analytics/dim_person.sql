select
    person_key
    , person_full_name
    , person_preferred_name
    , is_system_user
    , is_employee
    , is_salesperson
    , phone_number
    , email_address
from {{ ref('stg_application_person') }}
