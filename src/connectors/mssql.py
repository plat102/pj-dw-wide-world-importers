"""The source database. The only module in this project permitted to reach it.

Preconditions and the source version only -- reading the rows is dlt's job. The import-linter
contracts in pyproject.toml fail the build if anything else acquires the means to connect.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

import sqlalchemy as sa
from sqlalchemy.pool import NullPool

from utils.exceptions import ToolingError


def connection_string(source_db: str) -> str:
    raw = os.environ.get("MSSQL_CONNECTION_STRING")
    if not raw:
        raise ToolingError("MSSQL_CONNECTION_STRING is not set")
    parts = urlsplit(raw)
    return urlunsplit((parts.scheme, parts.netloc, f"/{source_db}", parts.query, parts.fragment))


def engine(conn_str: str) -> sa.Engine:
    # dlt round-robins the resources and each holds its connection across yields, so every
    # declared table is open at once -- past QueuePool's ceiling. NullPool has no ceiling.
    try:
        return sa.create_engine(conn_str, poolclass=NullPool)
    except sa.exc.ArgumentError as error:
        raise ToolingError(
            "MSSQL_CONNECTION_STRING is not a connection string -- expected "
            f"mssql+pymssql://LOGIN:PASSWORD@HOST:1433/ ({error})"
        ) from error


def check_declared_columns(source: sa.Engine, tables: list[dict]) -> None:
    """Assert every declared column exists; dlt's included_columns silently drops unknown names."""
    inspector = sa.inspect(source)
    problems = []
    for entry in tables:
        schema, table = entry["source"].split(".")
        actual = {c["name"] for c in inspector.get_columns(table, schema=schema)}
        for missing in sorted(set(entry["columns"]) - actual):
            problems.append(f"{entry['source']}.{missing}")
    if problems:
        raise ToolingError(
            "declared in the extraction contract but absent from the source: " + ", ".join(problems)
        )


def count_source_rows(source: sa.Engine, tables: list[dict]) -> dict[str, int]:
    """Row counts at the source. Row-level security filters silently, and usually partially."""
    counts: dict[str, int] = {}
    with source.connect() as conn:
        for entry in tables:
            schema, table = entry["source"].split(".")
            query = sa.text(f"SELECT COUNT(*) FROM [{schema}].[{table}]")
            counts[entry["output"]] = int(conn.execute(query).scalar_one())
    return counts


def assert_out_of_load_mode(conn: sa.Connection, source_db: str) -> None:
    """Refuse to extract a source still in DataLoadSimulation load mode.

    It switches versioning and the security policy off, so changed rows reach no history table.
    """
    # Every WWI history table is named `*_Archive`, so the counts agree unless versioning is off.
    versioned, archives = conn.execute(
        sa.text(
            "SELECT COUNT(CASE WHEN temporal_type = 2 THEN 1 END), "
            "       COUNT(CASE WHEN name LIKE '%[_]Archive' THEN 1 END) "
            "FROM sys.tables"
        )
    ).one()
    if versioned != archives:
        raise ToolingError(
            f"{source_db}: {versioned} versioned tables but {archives} archive tables -- "
            "the source is in load mode. Run "
            "DataLoadSimulation.ReactivateTemporalTablesAfterDataLoad and "
            "Configuration_RemoveDataLoadSimulationProcedures on the source, then extract again"
        )

    # WWI ships exactly one policy and load mode switches it off. Zero is also what a login
    # without VIEW DEFINITION sees, so both readings fail here.
    policies = conn.execute(
        sa.text("SELECT COUNT(*) FROM sys.security_policies WHERE is_enabled = 1")
    ).scalar()
    if policies != 1:
        raise ToolingError(
            f"{source_db}: {policies} enabled security policies, expected 1 -- either the "
            "source is in load mode (run "
            "DataLoadSimulation.Configuration_RemoveDataLoadSimulationProcedures), or this "
            "login cannot see them and needs GRANT VIEW DEFINITION on the database"
        )

    durability = conn.execute(
        sa.text("SELECT delayed_durability_desc FROM sys.databases WHERE name = :db"),
        {"db": source_db},
    ).scalar()
    if durability != "DISABLED":
        raise ToolingError(
            f"{source_db}: DELAYED_DURABILITY is {durability}, not DISABLED -- the source is "
            "still configured for bulk generation. Set it back, then extract again"
        )


def inspect_source(source: sa.Engine, source_db: str) -> str:
    """Check the preconditions and return the source version, which the extract reports."""
    with source.connect() as conn:
        exists = conn.execute(
            sa.text("SELECT 1 FROM sys.databases WHERE name = :db"), {"db": source_db}
        ).scalar()
        if exists is None:
            raise ToolingError(f"{source_db} does not exist, or this login cannot see it")

        assert_out_of_load_mode(conn, source_db)

        version = conn.execute(
            sa.text(
                "SELECT CAST(SERVERPROPERTY('ProductVersion') AS varchar(30)) + ' ' "
                "+ CAST(SERVERPROPERTY('ProductLevel') AS varchar(20)) + ' ' "
                "+ CAST(SERVERPROPERTY('Edition') AS varchar(60))"
            )
        ).scalar()
    if version is None:
        raise ToolingError("SERVERPROPERTY returned no version")
    return str(version)
