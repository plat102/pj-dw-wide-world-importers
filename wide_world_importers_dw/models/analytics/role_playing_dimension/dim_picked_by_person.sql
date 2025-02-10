{% set person_cols = dbt_utils.get_filtered_columns_in_relation(
    from=ref('dim_person'),
    except=['person_key', 'person_full_name', 'person_preferred_name',
            'is_system_user', 'is_employee', 'is_salesperson',]
) %}
select
    person_key as picked_by_person_key
    , person_full_name as picked_by_person_full_name
    , person_preferred_name as picked_by_picked_by_preferred_name
    {% for column in date_cols %}
        {{ column }} as picked_by_{{ column }} {% if not loop.last %},{% endif %}
    {% endfor %}
    , is_system_user
    , is_employee
    , is_salesperson
from {{ ref('dim_person')}}