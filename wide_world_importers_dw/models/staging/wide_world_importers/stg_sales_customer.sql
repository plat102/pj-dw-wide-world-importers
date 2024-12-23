{{ config(schema='stg') }}

with raw as (
    select
        CustomerID,
        CustomerName,
        BillToCustomerID
    from {{ source('wwi_raw', 'sales__Customers') }}
)
select * from raw

