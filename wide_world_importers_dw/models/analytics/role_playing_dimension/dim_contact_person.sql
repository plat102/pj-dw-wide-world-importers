
{% set person_cols = dbt_utils.get_filtered_columns_in_relation(
    from=ref('dim_person'),
    except=['person_key', 'person_full_name', 'person_preferred_name',
            'is_system_user', 'is_employee', 'is_salesperson',]
) %}
select
    person_key as contact_person_key
    , person_full_name as contact_full_name
    , person_preferred_name as contact_preferred_name
    {% for column in person_cols %}
        , {{ column }} as contact_{{ column }}
    {% endfor %}
    , is_system_user
    , is_employee
    , is_salesperson
from {{ ref('dim_person')}}
