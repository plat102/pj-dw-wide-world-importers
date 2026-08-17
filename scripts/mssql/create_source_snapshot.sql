-- Freeze the source into a read-only snapshot. Run prepare_extraction_login.sql FIRST:
-- a snapshot freezes metadata as well as data, so roles granted later never reach it.
--
--   sqlcmd -S localhost -U sa -C -v SOURCE_DB="WideWorldImporters" -v SNAPSHOT_DB="WWI_Snap" \
--          -v EXTRACT_LOGIN="wwi_extract" -i scripts/mssql/create_source_snapshot.sql

:on error exit

USE master;
GO

-- SNAPSHOT_DB is caller-supplied; dropping the source would be unrecoverable.
IF '$(SNAPSHOT_DB)' = '$(SOURCE_DB)'
BEGIN
    RAISERROR('SNAPSHOT_DB must differ from SOURCE_DB', 16, 1);
    SET NOEXEC ON;
END
GO

IF DB_ID('$(SNAPSHOT_DB)') IS NOT NULL
   AND (SELECT source_database_id FROM sys.databases WHERE name = '$(SNAPSHOT_DB)') IS NULL
BEGIN
    RAISERROR('%s exists and is a live database, not a snapshot; refusing to drop it', 16, 1, '$(SNAPSHOT_DB)');
    SET NOEXEC ON;
END
GO

IF DB_ID('$(SNAPSHOT_DB)') IS NOT NULL
    EXEC('DROP DATABASE [$(SNAPSHOT_DB)]');
GO

USE [$(SOURCE_DB)];
GO

-- A snapshot freezes role membership, so the login must be ready before this runs.
DECLARE @roles int, @territories int;
SELECT @roles = COUNT(*)
FROM sys.database_role_members m
JOIN sys.database_principals r ON m.role_principal_id = r.principal_id
JOIN sys.database_principals u ON m.member_principal_id = u.principal_id
WHERE u.name = '$(EXTRACT_LOGIN)' AND r.name LIKE '% Sales';

SELECT @territories = COUNT(DISTINCT SalesTerritory) FROM Application.StateProvinces;

IF @roles < @territories
BEGIN
    RAISERROR('%s holds %d of %d territory roles; run prepare_extraction_login.sql before creating the snapshot',
              16, 1, '$(EXTRACT_LOGIN)', @roles, @territories);
    SET NOEXEC ON;
END
GO

USE master;
GO

-- Sparse files go beside the source's own data files; the path is not assumed.
-- sysname needs COLLATE DATABASE_DEFAULT in the subquery or concatenation conflicts.
DECLARE @dir nvarchar(400);
SELECT TOP 1 @dir = LEFT(pn, LEN(pn) - CHARINDEX(sep, REVERSE(pn)) + 1)
FROM (
    SELECT CAST(physical_name AS nvarchar(400)) COLLATE DATABASE_DEFAULT AS pn,
           CASE WHEN CHARINDEX('\', physical_name) > 0 THEN '\' ELSE '/' END AS sep
    FROM sys.master_files
    WHERE database_id = DB_ID('$(SOURCE_DB)') AND type_desc = 'ROWS' AND file_id = 1
) AS primary_file;

DECLARE @files nvarchar(max) = N'';
SELECT @files = @files
     + CASE WHEN @files = N'' THEN N'' ELSE N', ' END
     + N'(NAME = [' + f.nm + N'], FILENAME = ''' + @dir + N'$(SNAPSHOT_DB)_'
     + f.nm + N'.ss'')'
FROM (
    SELECT CAST(name AS nvarchar(128)) COLLATE DATABASE_DEFAULT AS nm
    FROM sys.master_files
    WHERE database_id = DB_ID('$(SOURCE_DB)')
      AND type_desc = 'ROWS'       -- data files only; a snapshot has no log
) AS f;

DECLARE @sql nvarchar(max) =
    N'CREATE DATABASE [$(SNAPSHOT_DB)] ON ' + @files + N' AS SNAPSHOT OF [$(SOURCE_DB)];';
EXEC sp_executesql @sql;
GO

SELECT N'snapshot ' + CAST(name AS nvarchar(128)) COLLATE DATABASE_DEFAULT
     + N' is ' + CAST(state_desc AS nvarchar(60)) COLLATE DATABASE_DEFAULT AS status
FROM sys.databases WHERE name = '$(SNAPSHOT_DB)';
GO
