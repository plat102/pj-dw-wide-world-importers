with raw as (
    select *
    from {{ source('wwi_raw', 'sales__BuyingGroups') }}
)
select 
    BuyingGroupID AS buying_group_key
    , BuyingGroupName AS buying_group_name
from raw
