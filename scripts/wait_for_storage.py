#!/usr/bin/env python
"""Block until the object store can actually take a write, then prove it can be read back.

A container healthcheck is not enough. SeaweedFS reports healthy as soon as its master answers,
which happens **before** the volume server has re-registered its volumes after a restart -- so a
read one second later fails with a peer error rather than a 404. Anything that runs straight after
`make up`, CI most of all, needs a gate that waits for the store to be usable rather than reachable.

Deliberately speaks only the S3 API, so it stays true if the store behind the endpoint is replaced.

    uv run python scripts/wait_for_storage.py       # or: make up

Exits 0 once a round trip succeeds, 1 if the timeout passes first.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import duckdb

PROBE_KEY = "_probe/readiness.parquet"


def s3_connection(endpoint: str, access_key: str, secret_key: str, use_ssl: bool):
    conn = duckdb.connect()
    conn.execute("install httpfs")
    conn.execute("load httpfs")
    # Parameters are not accepted in CREATE SECRET, so the values are formatted in. They come from
    # the environment and never touch a tracked file.
    conn.execute(
        f"""
        create secret storage (
            type s3,
            key_id '{access_key}',
            secret '{secret_key}',
            endpoint '{endpoint}',
            url_style 'path',
            use_ssl {str(use_ssl).lower()}
        )
        """
    )
    return conn


def require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"{name} is not set -- copy .env.example to .env and fill it in")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=60.0, help="seconds to keep trying")
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between attempts")
    parser.add_argument("--quiet", action="store_true", help="print only on failure")
    args = parser.parse_args()

    endpoint = require("S3_ENDPOINT")
    bucket = require("S3_BUCKET")
    access_key = require("S3_ACCESS_KEY")
    secret_key = require("S3_SECRET_KEY")
    use_ssl = os.environ.get("S3_USE_SSL", "false").strip().lower() in {"1", "true", "yes"}

    target = f"s3://{bucket}/{PROBE_KEY}"
    deadline = time.monotonic() + args.timeout
    attempt = 0
    last_error = "no attempt was made"

    while time.monotonic() < deadline:
        attempt += 1
        try:
            conn = s3_connection(endpoint, access_key, secret_key, use_ssl)
            # A write and a read, not a listing. Listing a bucket succeeds while the volume
            # server is still unavailable, which is exactly the state this has to catch.
            conn.execute(f"copy (select 1 as ready) to '{target}' (format parquet)")
            rows = conn.execute(f"select ready from read_parquet('{target}')").fetchall()
            if rows != [(1,)]:
                raise RuntimeError(f"round trip returned {rows!r}")
            if not args.quiet:
                print(f"storage ready at {endpoint}, bucket {bucket} (attempt {attempt})")
            return 0
        except Exception as error:  # duckdb raises several unrelated types here
            last_error = f"{type(error).__name__}: {str(error).splitlines()[0]}"
            if not args.quiet:
                print(f"  attempt {attempt}: {last_error}")
            time.sleep(args.interval)

    print(
        f"storage at {endpoint} did not become writable within {args.timeout:.0f}s\n"
        f"  last error: {last_error}\n"
        f"  check `make storage_status`, and that the bucket {bucket!r} exists",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
