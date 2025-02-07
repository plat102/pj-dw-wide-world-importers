
select
    stg_warehouse_package_type.package_type_key AS package_type_key
    , stg_warehouse_package_type.package_type_name AS package_type_name
from {{ ref('stg_warehouse_package_type') }} 
