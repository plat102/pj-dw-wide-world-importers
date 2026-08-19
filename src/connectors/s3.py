"""The object store, over the S3 API.

Named for the protocol, not the product. SeaweedFS is what `docker-compose.yml` starts, and that
file is deliberately the only one that names it -- everything above sees `s3://` and environment
variables, so MinIO or real AWS S3 would need no change here.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import duckdb

from config import settings
from utils.exceptions import ToolingError

if TYPE_CHECKING:
    from s3fs import S3FileSystem


def client() -> S3FileSystem:
    """Path-style addressing, not virtual-host: no per-bucket DNS in front of a local store."""
    # Imported here rather than at module scope: s3fs costs about a second to import, and callers
    # that only want a DuckDB connection would otherwise pay it.
    import s3fs  # noqa: PLC0415

    return s3fs.S3FileSystem(
        key=settings.require("S3_ACCESS_KEY"),
        secret=settings.require("S3_SECRET_KEY"),
        client_kwargs={"endpoint_url": settings.endpoint_url()},
        config_kwargs={"s3": {"addressing_style": "path"}},
        skip_instance_cache=True,
    )


def load_secret(conn: duckdb.DuckDBPyConnection) -> None:
    """Give a DuckDB connection the store's credentials."""
    conn.execute(
        f"""
        create or replace secret storage (
            type s3,
            key_id '{settings.require("S3_ACCESS_KEY")}',
            secret '{settings.require("S3_SECRET_KEY")}',
            endpoint '{settings.require("S3_ENDPOINT")}',
            url_style 'path',
            use_ssl {str(settings.use_ssl()).lower()}
        )
        """
    )


def connection() -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB that can read and write `s3://`, with no lake attached."""
    conn = duckdb.connect()
    conn.execute("install httpfs")
    conn.execute("load httpfs")
    load_secret(conn)
    return conn


def wait_until_ready(timeout: float = 90.0, interval: float = 2.0) -> str:
    """Create the bucket and block until a write and a read both succeed.

    The container healthcheck goes green before the volume server can take a write, so a caller
    that trusts the healthcheck races the store. A real round trip is the only honest signal.
    """
    bucket = settings.bucket()
    endpoint = settings.require("S3_ENDPOINT")
    probe = f"{bucket}/.write-probe"
    deadline = time.monotonic() + timeout
    attempt = 0
    last_error = "no attempt completed"

    while time.monotonic() < deadline:
        attempt += 1
        try:
            fs = client()
            state = "already present"
            if not fs.exists(bucket):
                fs.mkdir(bucket)
                state = "created"
            fs.pipe_file(probe, b"ok")
            if fs.cat_file(probe) != b"ok":
                raise ToolingError("the store returned different bytes than were written")
            fs.rm_file(probe)
            return f"storage ready at {endpoint}, bucket {bucket} {state} (attempt {attempt})"
        # s3fs and botocore raise several unrelated types for an unready store, and the retry
        # loop treats them identically -- the deadline is what decides, not the type.
        except Exception as error:
            last_error = f"{type(error).__name__}: {str(error).splitlines()[0]}"
            time.sleep(interval)

    raise ToolingError(f"storage at {endpoint} not ready after {timeout:.0f}s: {last_error}")


def scalar(conn: duckdb.DuckDBPyConnection, sql: str) -> Any:
    """First column of the first row, for a query that must return one.

    `fetchone()` is typed as possibly None and eight call sites indexed it anyway. A query that
    comes back empty is a broken assumption, so it says so here rather than failing over there.
    """
    row = conn.execute(sql).fetchone()
    if row is None:
        raise ToolingError(f"expected one row, got none: {sql}")
    return row[0]
