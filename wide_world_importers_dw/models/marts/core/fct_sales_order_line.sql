with order_line_joined as (
    select
        stg_sales__order_lines.order_line_key as sales_order_line_key
        , stg_sales__order_lines.order_key as sales_order_key
        , stg_sales__order_lines.stock_item_key
        , stg_sales__order_lines.package_type_key
        , stg_sales__order_lines.quantity
        , stg_sales__order_lines.unit_price
        , stg_sales__order_lines.tax_rate
        , stg_sales__order_lines.picked_quantity
        , stg_sales__order_lines.picking_completed_at as sales_order_line_picking_completed_at
        , stg_sales__orders.customer_key
        -- Bill-to belongs on the fact, but Sales.Orders does not carry it: resolved here from
        -- the customer, once, on a unique key.
        , stg_sales__customers.bill_to_customer_key
        , stg_sales__orders.salesperson_key
        , stg_sales__orders.picked_by_person_key
        , stg_sales__orders.contact_person_key
        , stg_sales__orders.backorder_order_key
        , stg_sales__orders.order_date
        , stg_sales__orders.expected_delivery_date
        , stg_sales__orders.is_undersupply_backordered
        , stg_sales__orders.picking_completed_at as sales_order_picking_completed_at
        , stg_sales__order_lines.processed_at as sales_order_line_processed_at
    from {{ ref('stg_sales__order_lines') }}
    left join {{ ref('stg_sales__orders') }}
        on stg_sales__order_lines.order_key = stg_sales__orders.order_key
    left join {{ ref('stg_sales__customers') }}
        on stg_sales__orders.customer_key = stg_sales__customers.customer_key
)

-- dim_date is keyed on a yyyymmdd integer, so each date and timestamp becomes one here. The two
-- picking columns lose their time of day in the process; nothing downstream asks for it today.
select
    * exclude (
        order_date,
        expected_delivery_date,
        sales_order_picking_completed_at,
        sales_order_line_picking_completed_at
    ),
    cast(strftime(order_date, '%Y%m%d') as integer) as order_date_key,
    cast(strftime(expected_delivery_date, '%Y%m%d') as integer) as expected_delivery_date_key,
    cast(strftime(sales_order_picking_completed_at, '%Y%m%d') as integer) as sales_order_picking_completed_date_key,
    cast(strftime(sales_order_line_picking_completed_at, '%Y%m%d') as integer) as sales_order_line_picking_completed_date_key
from order_line_joined
