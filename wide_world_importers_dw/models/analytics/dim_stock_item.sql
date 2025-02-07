with dim_stock_item_stg as (
    select *
    from {{ref('stg_dim_stock_item_wwi')}}
)
select * from dim_stock_item_stg
