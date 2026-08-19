select
    package_type_key
    , package_type_name
from {{ ref('stg_warehouse_package_type') }}
