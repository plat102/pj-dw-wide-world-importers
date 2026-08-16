-- Drop the read-only snapshot created for an extraction run.
--   sqlcmd -S localhost -U sa -C -v SNAPSHOT_DB="WWI_Snap" -i scripts/mssql/drop_source_snapshot.sql

:on error exit

USE master;
GO

-- Only ever drops a snapshot; a live database has no source_database_id.
IF DB_ID('$(SNAPSHOT_DB)') IS NULL
    PRINT '$(SNAPSHOT_DB) does not exist';
ELSE IF (SELECT source_database_id FROM sys.databases WHERE name = '$(SNAPSHOT_DB)') IS NULL
    RAISERROR('%s is a live database, not a snapshot; refusing to drop it', 16, 1, '$(SNAPSHOT_DB)');
ELSE
BEGIN
    EXEC('DROP DATABASE [$(SNAPSHOT_DB)]');
    PRINT 'dropped $(SNAPSHOT_DB)';
END
GO
