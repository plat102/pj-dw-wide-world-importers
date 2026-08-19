with raw as (
    select *
    from {{ source('wwi_raw', 'application__people') }}
)

, raw__select_column as (
    select 
        person_id AS person_key
        , full_name AS person_full_name
        , preferred_name AS person_preferred_name
        , is_system_user AS is_system_user
        , is_employee AS is_employee
        , is_salesperson AS is_salesperson
        , phone_number AS phone_number
        , email_address AS email_address
    from raw
)

, raw__add_cursor_timestamp as (
    select 
        *
        , {{ snapshot_processed_at() }} as processed_at
    from raw__select_column
    -- cursor timestamp should be loaded time of the data into data lake
    -- this is just a workaround
)

select * from raw__add_cursor_timestamp
