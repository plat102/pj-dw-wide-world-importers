with raw as (
    select *
    from {{ source('wwi_raw', 'warehouse__Colors') }}
)
select
    ColorID AS color_key
    , ColorName AS color_name
from raw
