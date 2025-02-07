
select
    stg_application_person.person_key AS person_key
    , stg_application_person.person_full_name AS person_full_name
    , stg_application_person.person_preferred_name AS person_preferred_name
    , stg_application_person.is_system_user
    , stg_application_person.is_employee
    , stg_application_person.is_salesperson
    , stg_application_person.phone_number
    , stg_application_person.email_address
from {{ ref('stg_application_person') }} 
