with fact_sales_order_line as (
    select *
    from {{ref('stg_fact_sales_order_line_wwi')}}
)
select * from fact_sales_order_line
