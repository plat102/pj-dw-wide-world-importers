-- A catalog login that can read the lake and change nothing: SELECT on DuckLake's metadata tables,
-- no other privilege. Paired with the store's read-only identity, it is what a BI tool attaches
-- with, so a bug in that tool cannot write to the lake whatever it sends.
--
-- Run through `make catalog_reader`, inside the catalog container, as CATALOG_USER. Re-runnable:
-- an existing role keeps its grants and gets the current password.
--
--   psql variables: reader (role name), owner (the role that writes the catalog), metadata_schema
--   environment:    CATALOG_READER_PASSWORD, read with \getenv so it never sits in argv
\set ON_ERROR_STOP on
\getenv reader_password CATALOG_READER_PASSWORD
\if :{?reader_password}
\else
    \echo 'CATALOG_READER_PASSWORD is not set'
    \quit 1
\endif

select exists (select 1 from pg_roles where rolname = :'reader') as reader_exists \gset
\if :reader_exists
    alter role :"reader" with login password :'reader_password';
\else
    create role :"reader" with login password :'reader_password';
\endif

grant connect on database :"DBNAME" to :"reader";
grant usage on schema :"metadata_schema" to :"reader";
grant select on all tables in schema :"metadata_schema" to :"reader";
-- DuckLake can add metadata tables on a version upgrade; the writer creates them, so the default
-- is set for the writer's role, not for whoever runs this file.
alter default privileges for role :"owner" in schema :"metadata_schema"
    grant select on tables to :"reader";
