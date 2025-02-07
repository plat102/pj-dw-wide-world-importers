with dim_package_type_stg as (
    select *
    from {{ref('stg_dim_package_type_wwi')}}
)
select * from dim_package_type_stg
