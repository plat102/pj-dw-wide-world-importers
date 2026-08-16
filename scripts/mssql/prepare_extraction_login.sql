-- Read-only login for the extraction step (dlt: MSSQL -> Parquet).
--
-- Password is passed at run time, never stored here:
--   sqlcmd -S localhost -U sa -C \
--          -v EXTRACT_LOGIN="wwi_extract" -v EXTRACT_PASSWORD="$WWI_EXTRACT_PASSWORD" \
--          -i scripts/mssql/prepare_extraction_login.sql

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

-- Required by the extraction's single snapshot-isolation transaction.
ALTER DATABASE [WideWorldImporters] SET ALLOW_SNAPSHOT_ISOLATION ON;
GO

PRINT 'Login $(EXTRACT_LOGIN) ready: db_datareader, snapshot isolation on, no UNMASK.';
GO
