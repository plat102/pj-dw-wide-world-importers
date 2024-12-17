
-- 1 Account context
SELECT
    SUSER_NAME() AS LoginName,
    USER_NAME() AS UserName,
    DB_NAME() AS DatabaseName,
    HOST_NAME() AS HostName,
    APP_NAME() AS ApplicationName;

-- 2 Permissions: If this works, the issue might be with how the connection is being established (e.g., the application connection string).
USE [WideWorldImporters];
EXECUTE AS USER = 'airbyte_user';

-- Test access
SELECT * FROM Sales.Orders;
SELECT * FROM Purchasing.PurchaseOrders;

-- Revert context
REVERT;

