{{ config(
    materialized='table',
    schema='mart'
) }}

{% set fact_cols = dbt_utils.get_filtered_columns_in_relation(
        from=ref('fact_sales_order_line'),
        except=[]
    )
%}
{% set customer_cols = dbt_utils.get_filtered_columns_in_relation(
    from=ref('dim_customer'),
    except=['customer_key']
) %}
{% set person_cols = dbt_utils.get_filtered_columns_in_relation(
    from=ref('dim_person')
) %}
{% set stock_item_cols = dbt_utils.get_filtered_columns_in_relation(
    from=ref('dim_stock_item')
) %}
{% set package_type_cols = dbt_utils.get_filtered_columns_in_relation(
    from=ref('dim_package_type')
) %}
{% set date_cols = dbt_utils.get_filtered_columns_in_relation(
    from=ref('dim_date')
) %}

select
    {{ fact_cols | join(', fsol.') }},

    -- Customer details
    {% for column in customer_cols %}
        dim_customer.{{ column }} as customer_{{ column}}
        {% if not loop.last %},{% endif %}
    {% endfor %}
from {{ ref('fact_sales_order_line') }} fsol
left join {{ ref('dim_customer') }} dim_customer on fsol.customer_key = dim_customer.customer_key
