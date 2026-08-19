with order_line_joined as (
    select
        stg_sales_order_line.order_line_key as sales_order_line_key
        , stg_sales_order_line.order_key as sales_order_key
        , stg_sales_order_line.stock_item_key
        , stg_sales_order_line.package_type_key
        , stg_sales_order_line.quantity
        , stg_sales_order_line.unit_price
        , stg_sales_order_line.tax_rate
        , stg_sales_order_line.picked_quantity
        , stg_sales_order_line.picking_completed_date_key as sales_order_line_picking_completed_date_key
        , stg_sales_order.customer_key
        -- Bill-to belongs on the fact, not on the customer dimension: the mart used to reach
        -- it through dim_customer, which made the wide table depend on a dimension join to
        -- resolve one of its own keys. Sales.Orders does not carry it, so it is resolved here
        -- from the customer, once, on a unique key.
        , stg_sales_customer.bill_to_customer_key
        , stg_sales_order.salesperson_key
        , stg_sales_order.picked_by_person_key
        , stg_sales_order.contact_person_key
        , stg_sales_order.backorder_order_key
        , stg_sales_order.order_date_key
        , stg_sales_order.expected_delivery_date_key
        , stg_sales_order.is_undersupply_backordered
        , stg_sales_order.picking_completed_date_key as sales_order_picking_completed_date_key
        , stg_sales_order_line.processed_at as sales_order_line_processed_at
    from {{ ref('stg_sales_order_line') }}
    left join {{ ref('stg_sales_order') }}
        on stg_sales_order_line.order_key = stg_sales_order.order_key
    left join {{ ref('stg_sales_customer') }}
        on stg_sales_order.customer_key = stg_sales_customer.customer_key
)

-- Date keys arrive as dates and have to become the yyyymmdd integers dim_date is keyed on.
select
    * exclude (
        sales_order_line_picking_completed_date_key,
        order_date_key,
        expected_delivery_date_key,
        sales_order_picking_completed_date_key
    ),
    strftime(sales_order_line_picking_completed_date_key, '%Y%m%d') as sales_order_line_picking_completed_date_key,
    strftime(order_date_key, '%Y%m%d') as order_date_key,
    strftime(expected_delivery_date_key, '%Y%m%d') as expected_delivery_date_key,
    strftime(sales_order_picking_completed_date_key, '%Y%m%d') as sales_order_picking_completed_date_key
from order_line_joined
