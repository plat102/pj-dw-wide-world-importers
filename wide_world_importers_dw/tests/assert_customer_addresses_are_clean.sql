-- depends_on: {{ ref('dim_customer') }}

-- Both addresses are assembled from two source lines and land in the mart's contract: no stray
-- whitespace, and a missing address is NULL rather than an empty string.

select
    customer_key,
    '[' || delivery_address || ']' as delivery_address,
    '[' || postal_address || ']'   as postal_address
from {{ ref('dim_customer') }}
where delivery_address <> trim(delivery_address)
   or postal_address   <> trim(postal_address)
   or delivery_address = ''
   or postal_address   = ''
