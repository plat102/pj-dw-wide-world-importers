with raw as (
    select *
    from {{ source('wwi_raw', 'sales__buying_groups') }}
)
select 
    buying_group_id AS buying_group_key
    , buying_group_name AS buying_group_name
from raw
