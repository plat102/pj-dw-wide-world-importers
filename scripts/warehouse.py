"""Reach the object store and the warehouse. One definition of each, shared by every script.

`connect()` attaches only the catalog and the store, so a caller sees what any engine would.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import duckdb

EXTENSIONS = ("httpfs", "ducklake", "postgres")


def require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"{name} is not set -- copy .env.example to .env and fill it in")
    return value


def use_ssl() -> bool:
    return os.environ.get("S3_USE_SSL", "false").strip().lower() in {"1", "true", "yes"}


def endpoint_url() -> str:
    return f"{'https' if use_ssl() else 'http'}://{require('S3_ENDPOINT')}"


def s3fs_client():
    """An s3fs filesystem for the store. Path style, not virtual-host: no per-bucket DNS here."""
    # Imported here, not at the top: s3fs costs about a second to import, and every caller that
    # only wants catalog_dsn() or connect() would otherwise pay it.
    import s3fs  # noqa: PLC0415

    return s3fs.S3FileSystem(
        key=require("S3_ACCESS_KEY"),
        secret=require("S3_SECRET_KEY"),
        client_kwargs={"endpoint_url": endpoint_url()},
        config_kwargs={"s3": {"addressing_style": "path"}},
        skip_instance_cache=True,
    )


def scalar(conn: duckdb.DuckDBPyConnection, sql: str) -> Any:
    """The first column of the first row, for a query that must return one.

    `fetchone()` is typed as possibly None and every caller indexed it anyway. A query that comes
    back empty is a broken assumption, so it raises here rather than an IndexError over there.
    """
    row = conn.execute(sql).fetchone()
    if row is None:
        raise RuntimeError(f"expected one row, got none: {sql}")
    return row[0]


def load_s3_secret(conn: duckdb.DuckDBPyConnection) -> None:
    """Give a DuckDB connection the store's credentials, formatted in from the environment."""
    conn.execute(
        f"""
        create or replace secret storage (
            type s3,
            key_id '{require("S3_ACCESS_KEY")}',
            secret '{require("S3_SECRET_KEY")}',
            endpoint '{require("S3_ENDPOINT")}',
            url_style 'path',
            use_ssl {str(use_ssl()).lower()}
        )
        """
    )


def catalog_dsn() -> str:
    return (
        f"dbname={os.environ.get('CATALOG_DB', 'ducklake')} "
        f"host={os.environ.get('CATALOG_HOST', 'localhost')} "
        f"port={os.environ.get('CATALOG_PORT', '55432')} "
        f"user={require('CATALOG_USER')} "
        f"password={require('CATALOG_PASSWORD')}"
    )


def data_path() -> str:
    return f"s3://{require('S3_BUCKET')}/{os.environ.get('LAKE_PREFIX', 'lake')}/"


def store_connection() -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB that can read and write s3://, with no lake attached."""
    conn = duckdb.connect()
    conn.execute("install httpfs")
    conn.execute("load httpfs")
    load_s3_secret(conn)
    return conn


def connect() -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB with the store's credentials and the lake attached as `lake`."""
    conn = duckdb.connect()
    for extension in EXTENSIONS:
        conn.execute(f"install {extension}")
        conn.execute(f"load {extension}")
    load_s3_secret(conn)
    conn.execute(f"attach 'ducklake:postgres:{catalog_dsn()}' as lake (data_path '{data_path()}')")
    conn.execute("use lake")
    return conn
