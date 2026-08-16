-- Read-only login for the extraction. Password passed at run time, never stored here.
--   sqlcmd -S localhost -U sa -C -v EXTRACT_LOGIN="wwi_extract" \
--          -v EXTRACT_PASSWORD="$WWI_EXTRACT_PASSWORD" -i scripts/mssql/prepare_extraction_login.sql

:on error exit

USE master;
GO

IF EXISTS (SELECT 1 FROM sys.server_principals WHERE name = '$(EXTRACT_LOGIN)')
    DROP LOGIN [$(EXTRACT_LOGIN)];
GO

CREATE LOGIN [$(EXTRACT_LOGIN)] WITH PASSWORD = '$(EXTRACT_PASSWORD)';
GO

USE [WideWorldImporters];
GO

IF EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '$(EXTRACT_LOGIN)')
    DROP USER [$(EXTRACT_LOGIN)];
GO

CREATE USER [$(EXTRACT_LOGIN)] FOR LOGIN [$(EXTRACT_LOGIN)];
GO

-- SELECT only. No UNMASK: ingest masked values, unmask at the serving layer.
ALTER ROLE db_datareader ADD MEMBER [$(EXTRACT_LOGIN)];
GO

-- Sales.Customers is under RLS: without a territory role it reads as empty and raises
-- nothing. Joining the roles uses the security model instead of disabling it.
DECLARE @sql nvarchar(max) = N'';
SELECT @sql = @sql + N'ALTER ROLE ' + QUOTENAME(dp.name) + N' ADD MEMBER [$(EXTRACT_LOGIN)];' + CHAR(10)
FROM sys.database_principals dp
WHERE dp.type = 'R'
  AND dp.is_fixed_role = 0
  AND dp.name COLLATE DATABASE_DEFAULT IN (
      SELECT DISTINCT SalesTerritory COLLATE DATABASE_DEFAULT + N' Sales'
      FROM Application.StateProvinces);
IF @sql = N''
    RAISERROR('no "<territory> Sales" role matched; Sales.Customers would read as empty under RLS', 16, 1);
EXEC sp_executesql @sql;
GO

-- For ad-hoc reads only; the extraction reads a frozen snapshot instead.
ALTER DATABASE [WideWorldImporters] SET ALLOW_SNAPSHOT_ISOLATION ON;
GO

PRINT 'Login $(EXTRACT_LOGIN) ready: db_datareader, snapshot isolation on, no UNMASK.';
GO
