{{ config(
    materialized='table',
    schema='mart'
) }}

{% set fact_cols = dbt_utils.get_filtered_columns_in_relation(
        from=ref('fact_sales_order_line'),
        except=[
            'customer_key',
            'bill_to_customer_key'
            'salesperson_key', 'picked_by_person_key', 'contact_person_key',
            'stock_item_key',
            'package_type_key',
            'order_date_key', 'expected_delivery_date_key', 'sales_order_picking_completed_date_key', 'sales_order_line_picking_completed_date_key',
        ]
    )
%}
{% set customer_cols = dbt_utils.get_filtered_columns_in_relation(
    from=ref('dim_customer'),
    except=['customer_key', 'bill_to_customer_key', 'buying_group_key', 'delivery_city_key', 'postal_city_key'],
) %}
{% set person_cols = dbt_utils.get_filtered_columns_in_relation(
    from=ref('dim_person'),
    except=['person_key']
) %}
{% set stock_item_cols = dbt_utils.get_filtered_columns_in_relation(
    from=ref('dim_stock_item'),
    except=['stock_item_key']
) %}
{% set package_type_cols = dbt_utils.get_filtered_columns_in_relation(
    from=ref('dim_package_type'),
    except=['package_type_key']
) %}
{% set date_cols = dbt_utils.get_filtered_columns_in_relation(
    from=ref('dim_date'),
    except=['date_key']
) %}

select
    {{ fact_cols | join(', fsol.') }},

    -- Customer details
    {% for column in customer_cols %}
        dim_customer.{{ column }} as customer_{{ column}} {% if not loop.last %},{% endif %}
    {% endfor %}

    -- Bill to customer details
    , dim_bill_to_customer.customer_name as bill_to_customer_name

    -- Person details
    , dim_salesperson.person_full_name as salesperson_person_full_name
    , dim_picked_by_person.person_full_name as picked_by_person_person_full_name
    , dim_contact_person.person_full_name as contact_person_person_full_name

    -- Stock item details
    , dim_stock_item.stock_item_name
    , dim_stock_item.color_name
    , dim_stock_item.supplier_name
    , dim_stock_item.is_chiller_stock

    -- Package type details
    , dim_package_type.package_type_name as package_type_package_type_name
from {{ ref('fact_sales_order_line') }} as fsol
left join {{ ref('dim_customer') }}
    on fsol.customer_key = dim_customer.customer_key
left join {{ ref('dim_customer') }} as dim_bill_to_customer
    on dim_customer.bill_to_customer_key = dim_bill_to_customer.customer_key
left join {{ ref('dim_person') }} as dim_salesperson
    on fsol.salesperson_key = dim_salesperson.person_key
left join {{ ref('dim_person') }} as dim_picked_by_person
    on fsol.picked_by_person_key = dim_picked_by_person.person_key
left join {{ ref('dim_person') }} as dim_contact_person
    on fsol.contact_person_key = dim_contact_person.person_key
left join {{ ref('dim_stock_item') }}
    on fsol.stock_item_key = dim_stock_item.stock_item_key
left join {{ ref('dim_package_type') }}
    on fsol.package_type_key = dim_package_type.package_type_key
