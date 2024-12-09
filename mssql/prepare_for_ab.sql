
SELECT SERVERPROPERTY('IsIntegratedSecurityOnly') AS IsWindowsAuthOnly;

-- Step 1: Create a Login at the Server Level
CREATE LOGIN airbyte_user WITH PASSWORD = 'airbyte';

-- Step 2: Map the Login to a Database User in the Target Database
USE [WideWorldImporters]; 

CREATE USER airbyte_user FOR LOGIN airbyte_user;

-- Step 3: Grant Necessary Permissions
GRANT CONNECT TO airbyte_user;
-- Grant SELECT permission on all tables within the dbo schema.
-- GRANT SELECT ON SCHEMA::[dbo] TO airbyte_user;

GRANT SELECT ON SCHEMA::[Sales] TO airbyte_user;
EXEC sp_addrolemember 'db_datareader', 'airbyte_user';

-- Optional: Grant VIEW DEFINITION permission to allow Airbyte to read metadata.
GRANT VIEW DEFINITION ON DATABASE::[WideWorldImporters] TO airbyte_user;

-- Step 4: Verify Access (Optional)
SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'dbo';

SELECT name, is_disabled 
FROM sys.server_principals 
WHERE name = 'airbyte_user';


select * from Sales.Orders;

select * from Purchasing.PurchaseOrders;

