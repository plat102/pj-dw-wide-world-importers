with dim_person_stg as (
    select *
    from {{ref('stg_dim_person_wwi')}}
)
select * from dim_person_stg
