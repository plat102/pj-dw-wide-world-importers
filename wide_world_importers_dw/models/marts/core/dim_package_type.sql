select
    package_type_key
    , package_type_name
from {{ ref('stg_warehouse__package_types') }}
