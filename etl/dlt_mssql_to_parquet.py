"""Extract the WWI source into a Parquet snapshot, all tables in one SNAPSHOT transaction.

Connection from MSSQL_CONNECTION_STRING; a read-only login is enough.

    python etl/dlt_mssql_to_parquet.py --source-db WideWorldImporters
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import dlt
import yaml
from dlt.sources.sql_database import sql_table

REPO_ROOT = Path(__file__).resolve().parent.parent
TABLES_CONFIG = REPO_ROOT / "etl" / "tables.yml"
# sys.dm_exec_sessions.transaction_isolation_level: 5 is Snapshot.
SNAPSHOT_ISOLATION_LEVEL = 5


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-db", default="WideWorldImporters")
    p.add_argument("--output-dir", default="data/raw")
    return p.parse_args()


def connection_string(source_db: str) -> str:
    raw = os.environ.get("MSSQL_CONNECTION_STRING")
    if not raw:
        sys.exit("MSSQL_CONNECTION_STRING is not set")
    parts = urlsplit(raw)
    return urlunsplit((parts.scheme, parts.netloc, f"/{source_db}", parts.query, parts.fragment))


def pinned_engine(conn_str: str):
    """An engine on which one transaction can span every table dlt reads.

    StaticPool shares one session; AUTOCOMMIT makes pymssql ignore SQLAlchemy's rollback on close.
    """
    import sqlalchemy as sa
    from sqlalchemy.pool import StaticPool

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
        sys.exit(
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
        sys.exit(
            f"the snapshot transaction did not survive the extraction (began {expected}, ended "
            f"{actual}) -- the tables are not from one instant. Something in the driver, the "
            "pool or the extraction library issued its own commit or rollback; the settings in "
            "pinned_engine() are what prevent that"
        )


def check_declared_columns(engine, tables: list[dict]) -> None:
    """Assert every declared column exists; dlt's included_columns silently drops unknown names."""
    import sqlalchemy as sa

    inspector = sa.inspect(engine)
    problems = []
    for entry in tables:
        schema, table = entry["source"].split(".")
        actual = {c["name"] for c in inspector.get_columns(table, schema=schema)}
        for missing in sorted(set(entry["columns"]) - actual):
            problems.append(f"{entry['source']}.{missing}")
    if problems:
        sys.exit("declared in etl/tables.yml but absent from the source: " + ", ".join(problems))


def count_source_rows(engine, tables: list[dict]) -> dict[str, int]:
    """Source row counts, to catch row-level security filtering part of a table."""
    import sqlalchemy as sa

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
    import sqlalchemy as sa

    # Every WWI history table is named `*_Archive`, so the counts agree unless versioning is off.
    versioned, archives = conn.execute(
        sa.text(
            "SELECT COUNT(CASE WHEN temporal_type = 2 THEN 1 END), "
            "       COUNT(CASE WHEN name LIKE '%[_]Archive' THEN 1 END) "
            "FROM sys.tables"
        )
    ).fetchone()
    if versioned != archives:
        sys.exit(
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
        sys.exit(
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
        sys.exit(
            f"{source_db}: DELAYED_DURABILITY is {durability}, not DISABLED -- the source is "
            "still configured for bulk generation. Set it back, then extract again"
        )


def inspect_source(conn_str: str, source_db: str) -> dict[str, str]:
    """Check the preconditions and read the facts the manifest needs.

    On a plain connection: the isolation check needs there to be no transaction yet.
    """
    import sqlalchemy as sa

    engine = sa.create_engine(conn_str)
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "SELECT snapshot_isolation_state_desc FROM sys.databases WHERE name = :db"
            ),
            {"db": source_db},
        ).fetchone()
        if row is None:
            sys.exit(f"{source_db} does not exist, or this login cannot see it")
        if row[0] != "ON":
            sys.exit(
                f"{source_db}: ALLOW_SNAPSHOT_ISOLATION is {row[0]}, not ON -- the extraction "
                "reads every table in one snapshot transaction and will not fall back to READ "
                "COMMITTED. Run scripts/mssql/prepare_extraction_login.sql to enable it"
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
    return {
        "mssql_version": version,
        # Without the computed column, on-time has to be parsed from ReturnedDeliveryData instead.
        "delivery_time_form": "computed_column" if computed else "raw_json",
    }


def clear_previous_run(out_dir: Path) -> None:
    """Delete only what a previous extraction wrote; rmtree would take the manifest too."""
    for path in out_dir.glob("*.parquet"):
        path.unlink()
    (out_dir / "_extraction.json").unlink(missing_ok=True)
    shutil.rmtree(out_dir / "_dlt", ignore_errors=True)


def main() -> int:
    args = parse_args()
    config = yaml.safe_load(TABLES_CONFIG.read_text(encoding="utf-8"))
    tables = config["tables"]
    schema_version = config["schema_version"]

    conn_str = connection_string(args.source_db)
    source_facts = inspect_source(conn_str, args.source_db)

    engine = pinned_engine(conn_str)
    raw, cursor, transaction_id = open_snapshot_transaction(engine)
    check_declared_columns(engine, tables)
    source_counts = count_source_rows(engine, tables)

    load_timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    clear_previous_run(out_dir)

    # Staged locally so the manifest's SHA256 covers exactly the bytes `seed_bronze` uploads.
    staging = out_dir / "_dlt"
    pipeline = dlt.pipeline(
        pipeline_name="wwi_snapshot",
        destination=dlt.destinations.filesystem(bucket_url=staging.as_uri()),
        dataset_name="raw",
        progress=None,
    )

    resources = []
    for entry in tables:
        schema, table = entry["source"].split(".")
        resources.append(
            sql_table(
                credentials=engine,
                schema=schema,
                table=table,
                included_columns=entry["columns"],
                backend="pyarrow",
                reflection_level="full_with_precision",
                write_disposition="replace",
            ).with_name(entry["output"])
        )

    # Split rather than `pipeline.run` so the transaction ends with the reads. workers=1 is
    # correctness, not speed: all resources share one connection.
    pipeline.extract(resources, loader_file_format="parquet", workers=1)

    # Before anything is published: the files would be each valid and collectively wrong.
    assert_same_transaction(cursor, transaction_id)
    cursor.execute("COMMIT TRANSACTION")
    raw.close()

    pipeline.normalize()
    print(pipeline.load())

    written = flatten_output(staging, out_dir, tables)

    drift = {n: (source_counts[n], written[n]) for n in written if source_counts[n] != written[n]}
    if drift:
        detail = ", ".join(f"{n}: source {a:,} vs parquet {b:,}" for n, (a, b) in sorted(drift.items()))
        sys.exit(f"row counts do not match the source: {detail}")
    (out_dir / "_extraction.json").write_text(
        json.dumps(
            {
                "schema_version": schema_version,
                "load_timestamp": load_timestamp,
                "source_database": args.source_db,
                **source_facts,
                "files": written,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n{len(written)} tables written to {out_dir}/ at load_timestamp {load_timestamp}")
    return 0


def flatten_output(staging: Path, out_dir: Path, tables: list[dict]) -> dict[str, int]:
    """dlt writes <dataset>/<table>/<load_id>.<id>.parquet; the contract wants one flat file."""
    import pyarrow.parquet as pq

    written: dict[str, int] = {}
    missing = [e["output"] for e in tables if not list(staging.rglob(f"{e['output']}/*.parquet"))]
    if missing:
        # Row-level security filters silently; a missing file is never success.
        sys.exit(f"no parquet produced for: {', '.join(missing)}")

    for entry in tables:
        name = entry["output"]
        parts = sorted(staging.rglob(f"{name}/*.parquet"))
        target = out_dir / f"{name}.parquet"
        if len(parts) == 1:
            shutil.move(str(parts[0]), target)
        else:
            table = pq.read_table([str(p) for p in parts])
            pq.write_table(table, target, compression="snappy")
        rows = pq.ParquetFile(target).metadata.num_rows
        if rows == 0:
            sys.exit(f"{name} extracted 0 rows; every declared table must carry data")
        written[name] = rows
    shutil.rmtree(staging, ignore_errors=True)
    return written


if __name__ == "__main__":
    raise SystemExit(main())
