
with fact_sales_order_line as (
    select 
        stg_sales_order_line.order_line_key AS sales_order_line_key
        , stg_sales_order_line.order_key AS sales_order_key
        , stg_sales_order_line.stock_item_key
        , stg_sales_order_line.package_type_key
        , stg_sales_order_line.quantity
        , stg_sales_order_line.unit_price
        , stg_sales_order_line.tax_rate
        , stg_sales_order_line.picked_quantity
        , stg_sales_order_line.picking_completed_date_key AS sales_order_line_picking_completed_date_key
        , stg_sales_order.customer_key
        , stg_sales_order.salesperson_key
        , stg_sales_order.picked_by_person_key
        , stg_sales_order.contact_person_key
        , stg_sales_order.backorder_order_key
        , stg_sales_order.order_date_key
        , stg_sales_order.expected_delivery_date_key
        , stg_sales_order.is_undersupply_backordered AS is_undersupply_backordered
        , stg_sales_order.picking_completed_date_key AS sales_order_picking_completed_date_key
        , stg_sales_order_line.processed_at AS sales_order_line_processed_at
    from {{ ref('stg_sales_order_line') }}
    left join {{ ref('stg_sales_order') }} on stg_sales_order_line.order_key = stg_sales_order.order_key
)

, fact_sales_order_line__format_date as (
    select 
        * except (
            sales_order_line_picking_completed_date_key,
            order_date_key,
            expected_delivery_date_key,
            sales_order_picking_completed_date_key
        ),
        format_date('%Y%m%d', sales_order_line_picking_completed_date_key) as sales_order_line_picking_completed_date_key,
        format_date('%Y%m%d', order_date_key) as order_date_key,
        format_date('%Y%m%d', expected_delivery_date_key) as expected_delivery_date_key,
        format_date('%Y%m%d', sales_order_picking_completed_date_key) as sales_order_picking_completed_date_key
    from fact_sales_order_line
)

select * from fact_sales_order_line__format_date
