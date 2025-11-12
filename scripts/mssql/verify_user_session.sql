SELECT
    session_id,
    login_name,
    host_name,
    database_id,
    client_interface_name
FROM
    sys.dm_exec_sessions
WHERE
    login_name = 'airbyte_user';


SELECT
    session_id,
    login_name,
    host_name,
    database_id,
    client_interface_name,
--     auth_scheme,          -- Windows or SQL Server authentication
    is_user_process,
    original_login_name,  -- The actual login used
    program_name
FROM
    sys.dm_exec_sessions
WHERE
    session_id = @@SPID or login_name = 'airbyte_user';
