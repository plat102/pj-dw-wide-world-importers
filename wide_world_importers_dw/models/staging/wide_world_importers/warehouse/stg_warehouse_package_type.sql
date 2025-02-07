with raw as (
    select *
    from {{ source('wwi_raw', 'warehouse__PackageTypes') }}
)
select
    PackageTypeID AS package_type_key
    , PackageTypeName AS package_type_name
from raw
