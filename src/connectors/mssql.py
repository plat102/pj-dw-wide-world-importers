"""The source database. The only module in this project permitted to reach it.

Everything here needs a credential; nothing downstream of the snapshot does, and the import-linter
contracts in pyproject.toml fail the build if anything else acquires the means to connect.

Consistency comes from one snapshot-isolation transaction spanning every table, not from locking:
`open_snapshot_transaction` opens it and `assert_same_transaction` proves it never silently reopened
part-way through, which would publish two moments as one snapshot.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

import sqlalchemy as sa
from sqlalchemy.pool import StaticPool

from utils.exceptions import ToolingError

# sys.dm_exec_sessions.transaction_isolation_level: 5 is Snapshot.
SNAPSHOT_ISOLATION_LEVEL = 5


def connection_string(source_db: str) -> str:
    raw = os.environ.get("MSSQL_CONNECTION_STRING")
    if not raw:
        raise ToolingError("MSSQL_CONNECTION_STRING is not set")
    parts = urlsplit(raw)
    return urlunsplit((parts.scheme, parts.netloc, f"/{source_db}", parts.query, parts.fragment))


def pinned_engine(conn_str: str):
    """An engine on which one transaction can span every table dlt reads.

    StaticPool shares one session; AUTOCOMMIT makes pymssql ignore SQLAlchemy's rollback on close.
    """
    return sa.create_engine(
        conn_str,
        poolclass=StaticPool,
        isolation_level="AUTOCOMMIT",
        pool_reset_on_return=None,
    )


def open_snapshot_transaction(engine):
    """Begin the transaction every table is read inside. Returns the raw connection and its id.

    SNAPSHOT is set and read back before BEGIN: SQL Server refuses to switch afterwards (Msg 3951).
    """
    raw = engine.raw_connection()
    cursor = raw.cursor()
    cursor.execute("SET TRANSACTION ISOLATION LEVEL SNAPSHOT")
    # Own session only, so this needs no permission the extraction login lacks.
    cursor.execute(
        "SELECT transaction_isolation_level FROM sys.dm_exec_sessions WHERE session_id = @@SPID"
    )
    level = cursor.fetchone()[0]
    if level != SNAPSHOT_ISOLATION_LEVEL:
        raise ToolingError(
            f"the session is at isolation level {level}, not {SNAPSHOT_ISOLATION_LEVEL} "
            "(snapshot) -- SET TRANSACTION ISOLATION LEVEL SNAPSHOT did not take effect"
        )
    cursor.execute("BEGIN TRANSACTION")
    cursor.execute("SELECT CURRENT_TRANSACTION_ID()")
    return raw, cursor, cursor.fetchone()[0]


def assert_same_transaction(cursor, expected: int) -> None:
    """Refuse to publish a snapshot whose reads were not all in one transaction.

    A changed id means different instants -- invisible downstream, since each file is valid.
    """
    cursor.execute("SELECT CURRENT_TRANSACTION_ID()")
    actual = cursor.fetchone()[0]
    if actual != expected:
        raise ToolingError(
            f"the snapshot transaction did not survive the extraction (began {expected}, ended "
            f"{actual}) -- the tables are not from one instant. Something in the driver, the "
            "pool or the extraction library issued its own commit or rollback; the settings in "
            "pinned_engine() are what prevent that"
        )


def check_declared_columns(engine, tables: list[dict]) -> None:
    """Assert every declared column exists; dlt's included_columns silently drops unknown names."""
    inspector = sa.inspect(engine)
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


def count_source_rows(engine, tables: list[dict]) -> dict[str, int]:
    """Source row counts, to catch row-level security filtering part of a table."""
    counts = {}
    with engine.connect() as conn:
        for entry in tables:
            schema, table = entry["source"].split(".")
            counts[entry["output"]] = conn.execute(
                sa.text(f"SELECT COUNT(*) FROM [{schema}].[{table}]")
            ).scalar()
    return counts


def assert_out_of_load_mode(conn, source_db: str) -> None:
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
    ).fetchone()
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


def inspect_source(conn_str: str, source_db: str) -> dict[str, str]:
    """Check the preconditions and read the facts the manifest needs.

    On a plain connection: the isolation check needs there to be no transaction yet.
    """
    engine = sa.create_engine(conn_str)
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT snapshot_isolation_state_desc FROM sys.databases WHERE name = :db"
            ),
            {"db": source_db},
        ).fetchone()
        if row is None:
            raise ToolingError(f"{source_db} does not exist, or this login cannot see it")
        if row[0] != "ON":
            raise ToolingError(
                f"{source_db}: ALLOW_SNAPSHOT_ISOLATION is {row[0]}, not ON -- the extraction "
                "reads every table in one snapshot transaction and will not fall back to READ "
                "COMMITTED. Run infrastructure/mssql/prepare_extraction_login.sql to enable it"
            )

        assert_out_of_load_mode(conn, source_db)

        version = conn.execute(
            sa.text(
                "SELECT CAST(SERVERPROPERTY('ProductVersion') AS varchar(30)) + ' ' "
                "+ CAST(SERVERPROPERTY('ProductLevel') AS varchar(20)) + ' ' "
                "+ CAST(SERVERPROPERTY('Edition') AS varchar(60))"
            )
        ).scalar()
        computed = conn.execute(
            sa.text(
                "SELECT COUNT(*) FROM sys.computed_columns "
                "WHERE object_id = OBJECT_ID('Sales.Invoices') AND name = 'ConfirmedDeliveryTime'"
            )
        ).scalar()
    if version is None:
        raise ToolingError(
            "SERVERPROPERTY returned no version -- the manifest records it, so it must exist"
        )
    return {
        "mssql_version": str(version),
        # Without the computed column, on-time has to be parsed from ReturnedDeliveryData instead.
        "delivery_time_form": "computed_column" if computed else "raw_json",
    }
