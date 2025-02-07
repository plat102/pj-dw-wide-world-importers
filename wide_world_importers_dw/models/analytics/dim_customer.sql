with dim_customer_stg as (
    select *
    from {{ref('stg_dim_customer_wwi')}}
)
select * from dim_customer_stg
