-- Step 1: Clean up existing login and user if they exist
USE master
GO
IF EXISTS (SELECT * FROM sys.server_principals WHERE name = 'airbyte_user')
    DROP LOGIN airbyte_user;

USE [WideWorldImporters]
GO
IF EXISTS (SELECT * FROM sys.database_principals WHERE name = 'airbyte_user')
    DROP USER airbyte_user;

-- Step 2: Create a new login and user
USE master
GO
CREATE LOGIN airbyte_user WITH PASSWORD = 'airbyte';
USE [WideWorldImporters]
GO
CREATE USER airbyte_user FOR LOGIN airbyte_user;

-- Step 3: Grant necessary permissions
USE [WideWorldImporters]
GO
EXEC sp_addrolemember 'db_datareader', 'airbyte_user';

-- Grant SELECT on all tables and views in all schemas of the database
-- GRANT SELECT ON DATABASE::[WideWorldImporters] TO airbyte_user;

-- Grant VIEW DEFINITION to allow metadata access
-- GRANT VIEW DEFINITION ON DATABASE::[WideWorldImporters] TO airbyte_user;


-- Step 4: Verify user access by running queries
-- Test that the user can access data
EXECUTE AS LOGIN = 'airbyte_user'
GO

-- Test queries for two schemas (Sales and Website)
SELECT TOP 5 * FROM Sales.Orders
GO

-- Check the effective permissions for the user
-- SELECT * FROM fn_my_permissions(NULL, 'DATABASE');
-- SELECT * FROM fn_my_permissions('Sales.Orders', 'OBJECT');

-- Revert to your original session
REVERT;

-- Step 5: End of script
PRINT 'airbyte_user has been successfully created and configured.';


-- !!!!! Disable the SECURITY POLICY and MASKING POLICY for the user to access the data FilterCustomersBySalesTerritoryRole
-- https://stackoverflow.com/questions/39065271/enable-disable-a-security-policy-in-sql-server
