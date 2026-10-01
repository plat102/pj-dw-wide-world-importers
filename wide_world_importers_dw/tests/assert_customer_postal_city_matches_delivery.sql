-- depends_on: {{ ref('dim_customer') }}

-- postal_city_key is carried without attributes, which is only honest while it never differs
-- from delivery_city_key. The day it does, this fails and the second city join gets built.

select customer_key, delivery_city_key, postal_city_key
from {{ ref('dim_customer') }}
where postal_city_key is distinct from delivery_city_key
