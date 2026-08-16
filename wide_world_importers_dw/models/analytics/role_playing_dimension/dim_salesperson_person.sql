
{{
  config(
    materialized = 'view',
    )
}}

{% set person_cols = dbt_utils.get_filtered_columns_in_relation(
    from=ref('dim_person'),
    except=['person_key', 'person_full_name', 'person_preferred_name',
            'is_system_user', 'is_employee', 'is_salesperson',]
) %}
select
    person_key as salesperson_person_key
    , person_full_name as salesperson_full_name
    , person_preferred_name as salesperson_preferred_name
    {% for column in person_cols %}
        , {{ column }} as salesperson_{{ column }}
    {% endfor %}
    , is_system_user
    , is_employee
    , is_salesperson
from {{ ref('dim_person')}}
where is_salesperson = true
