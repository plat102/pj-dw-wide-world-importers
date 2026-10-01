-- Read-only login for the extraction. Password passed at run time, never stored here.
--   sqlcmd -S localhost -U sa -C -v EXTRACT_LOGIN="wwi_extract" \
--          -v EXTRACT_PASSWORD="$WWI_EXTRACT_PASSWORD" -i infrastructure/mssql/prepare_extraction_login.sql

:on error exit

USE master;
GO

-- Safe to rerun. ALTER rather than DROP + CREATE: DROP LOGIN fails while the login has a session
-- open -- an extract running, a client left connected -- and `:on error exit` then stops the
-- script halfway, with the login gone and no user.
IF EXISTS (SELECT 1 FROM sys.server_principals WHERE name = '$(EXTRACT_LOGIN)')
    ALTER LOGIN [$(EXTRACT_LOGIN)] WITH PASSWORD = '$(EXTRACT_PASSWORD)';
ELSE
    CREATE LOGIN [$(EXTRACT_LOGIN)] WITH PASSWORD = '$(EXTRACT_PASSWORD)';
GO

USE [WideWorldImporters];
GO

-- An existing user is re-mapped rather than dropped: a login created again elsewhere gets a new
-- SID, and a user still holding the old one is orphaned.
IF EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '$(EXTRACT_LOGIN)')
    ALTER USER [$(EXTRACT_LOGIN)] WITH LOGIN = [$(EXTRACT_LOGIN)];
ELSE
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
EXEC sp_executesql @sql;
GO

-- Every territory, not just some: a territory with no matching role, or one this login did not
-- join, hides its customers under RLS without an error. The extract refuses that too, by
-- comparing COUNT(*) with sys.partitions, but failing here names the territory.
DECLARE @missing nvarchar(2000) = (
    SELECT STRING_AGG(CAST(t.SalesTerritory AS nvarchar(max)), N', ')
    FROM (SELECT DISTINCT SalesTerritory FROM Application.StateProvinces) AS t
    WHERE NOT EXISTS (
        SELECT 1
        FROM sys.database_role_members AS rm
        JOIN sys.database_principals AS r ON r.principal_id = rm.role_principal_id
        JOIN sys.database_principals AS m ON m.principal_id = rm.member_principal_id
        WHERE m.name = '$(EXTRACT_LOGIN)'
          AND r.name COLLATE DATABASE_DEFAULT = t.SalesTerritory COLLATE DATABASE_DEFAULT + N' Sales'));
IF @missing IS NOT NULL
    RAISERROR('$(EXTRACT_LOGIN) is in no "<territory> Sales" role for: %s -- those customers would read as empty under RLS', 16, 1, @missing);
GO

-- Metadata only. Without it sys.security_policies returns zero rows and raises nothing, so the
-- extraction's load-mode guard would pass everything.
GRANT VIEW DEFINITION TO [$(EXTRACT_LOGIN)];
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

PRINT 'Login $(EXTRACT_LOGIN) ready: db_datareader, VIEW DEFINITION, no UNMASK, no write of any kind.';
GO
