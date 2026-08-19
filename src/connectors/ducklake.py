"""The DuckLake lakehouse: Parquet on the object store, catalog in Postgres.

Named for the product, unlike `s3`, because it is product-specific: the ATTACH form and the
`ducklake_*` table functions exist nowhere else.
"""

from __future__ import annotations

import duckdb

from config import settings
from connectors import s3

EXTENSIONS = ("httpfs", "ducklake", "postgres")
CATALOG = "lake"


def connect() -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB with the store's credentials and the lake attached as `lake`.

    Attaches the catalog and the store and nothing else, so a caller sees what any engine reaching
    this lakehouse would see -- not a local file that happens to have the answers cached.
    """
    conn = duckdb.connect()
    for extension in EXTENSIONS:
        conn.execute(f"install {extension}")
        conn.execute(f"load {extension}")
    s3.load_secret(conn)
    conn.execute(
        f"attach 'ducklake:postgres:{settings.catalog_dsn()}' as {CATALOG} "
        f"(data_path '{settings.data_path()}')"
    )
    conn.execute(f"use {CATALOG}")
    return conn


def latest_snapshot(conn: duckdb.DuckDBPyConnection) -> int:
    """The newest lake snapshot number. Three modules asked this question separately."""
    return int(s3.scalar(conn, f"select max(snapshot_id) from ducklake_snapshots('{CATALOG}')"))


def relations(conn: duckdb.DuckDBPyConnection, table_type: str | None = None) -> list[tuple]:
    """Every relation in the lake as (schema, name, type), optionally filtered to one type."""
    sql = (
        "select table_schema, table_name, table_type from information_schema.tables "
        f"where table_catalog = '{CATALOG}'"
    )
    if table_type is not None:
        sql += f" and table_type = '{table_type}'"
    return conn.execute(sql + " order by table_schema, table_name").fetchall()


def relation_count(conn: duckdb.DuckDBPyConnection, table_type: str | None = None) -> int:
    sql = f"select count(*) from information_schema.tables where table_catalog = '{CATALOG}'"
    if table_type is not None:
        sql += f" and table_type = '{table_type}'"
    return int(s3.scalar(conn, sql))
