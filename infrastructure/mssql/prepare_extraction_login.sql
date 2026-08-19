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

-- Metadata only. Without it sys.security_policies returns zero rows and raises nothing, so the
-- extraction's load-mode guard would pass everything.
GRANT VIEW DEFINITION TO [$(EXTRACT_LOGIN)];
GO

-- Required, not optional: the extraction reads every table in one snapshot transaction and
-- refuses to fall back to READ COMMITTED. The database ships with this OFF.
ALTER DATABASE [WideWorldImporters] SET ALLOW_SNAPSHOT_ISOLATION ON;
GO

-- Prove the guard can see rather than asserting it. USER, not LOGIN: VIEW DEFINITION and
-- sys.security_policies are both database-scoped.
EXECUTE AS USER = '$(EXTRACT_LOGIN)';
DECLARE @policies int = (SELECT COUNT(*) FROM sys.security_policies WHERE is_enabled = 1);
REVERT;
IF @policies = 0
    RAISERROR('$(EXTRACT_LOGIN) reads 0 enabled security policies; VIEW DEFINITION did not take effect', 16, 1);
PRINT 'Guard visibility confirmed: security policies visible to $(EXTRACT_LOGIN).';
GO

PRINT 'Login $(EXTRACT_LOGIN) ready: db_datareader, VIEW DEFINITION, snapshot isolation on, no UNMASK.';
GO
