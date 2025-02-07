with raw as (
    select *
    from {{ source('wwi_raw', 'application__People') }}
)

, raw__select_column as (
    select 
        PersonID AS person_key
        , FullName AS person_full_name
        , PreferredName AS person_preferred_name
        , IsSystemUser AS is_system_user
        , IsEmployee AS is_employee
        , IsSalesperson AS is_salesperson
        , PhoneNumber AS phone_number
        , EmailAddress AS email_address
    from raw
)

, raw__add_cursor_timestamp as (
    select 
        *
        , current_timestamp() as processed_at
    from raw__select_column
    -- cursor timestamp should be loaded time of the data into data lake
    -- this is just a workaround
)

select * from raw__add_cursor_timestamp
