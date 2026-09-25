"""The DuckLake lakehouse: Parquet on the object store, catalog in Postgres.

Every layer is a schema of one lake -- bronze, which dlt writes, and the schemas dbt builds.
"""

from __future__ import annotations

import duckdb

from config import settings
from connectors import s3
from utils.exceptions import ToolingError

EXTENSIONS = ("httpfs", "ducklake", "postgres")
CATALOG = "lake"


def connect() -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB with the store's credentials and the lake attached as `lake`.

    Nothing else is attached, so a caller sees what any engine reaching this lakehouse would see.
    """
    conn = duckdb.connect()
    for extension in EXTENSIONS:
        conn.execute(f"install {extension}")
        conn.execute(f"load {extension}")
    s3.load_secret(conn)
    # The metadata schema is stated, not inherited from the role's search path: dlt states it too,
    # and that is what makes both halves provably one lake.
    conn.execute(
        f"attach 'ducklake:postgres:{settings.catalog_dsn()}' as {CATALOG} "
        f"(data_path '{settings.data_path()}', metadata_schema '{settings.METADATA_SCHEMA}')"
    )
    conn.execute(f"use {CATALOG}")
    return conn


def latest_snapshot(conn: duckdb.DuckDBPyConnection) -> int:
    """The newest lake snapshot number."""
    return int(s3.scalar(conn, f"select max(snapshot_id) from ducklake_snapshots('{CATALOG}')"))


def relations(
    conn: duckdb.DuckDBPyConnection, table_type: str | None = None
) -> list[tuple[str, str, str]]:
    """Every relation in the lake as (schema, name, type), optionally filtered to one type.

    dlt's own bookkeeping tables are left out: they sit in the bronze schema but are not data.
    """
    sql = (
        "select table_schema, table_name, table_type from information_schema.tables "
        f"where table_catalog = '{CATALOG}' and not starts_with(table_name, '_dlt')"
    )
    if table_type is not None:
        sql += f" and table_type = '{table_type}'"
    return conn.execute(sql + " order by table_schema, table_name").fetchall()


def row_counts(
    conn: duckdb.DuckDBPyConnection, schema: str, tables: list[str]
) -> dict[str, int]:
    """Row count per table, read back through an attach of its own, independent of dlt's."""
    present = {name for found, name, _ in relations(conn) if found == schema}
    missing = sorted(set(tables) - present)
    if missing:
        raise ToolingError(
            f"{CATALOG}.{schema} does not hold {', '.join(missing)} -- the load reported success, "
            "so this attach is reaching a different lake than the one dlt wrote to"
        )
    query = " union all ".join(
        f"select '{name}', count(*) from {CATALOG}.\"{schema}\".\"{name}\"" for name in tables
    )
    return dict(conn.execute(query).fetchall())
