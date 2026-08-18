#!/usr/bin/env python
"""Create the bucket if it is missing, then block until the store can take a write.

A healthcheck is not enough: the store reports healthy before it can serve a write. Creating the
bucket over the S3 API keeps the step store-agnostic.

    python -m scripts.wait_for_storage       # or: make up
"""

from __future__ import annotations

import argparse
import sys
import time

from scripts.warehouse import require, s3fs_client

PROBE_KEY = "_probe/readiness"


def probe(bucket: str) -> str:
    """Create the bucket if needed, then round-trip an object. Raises until the store is ready.

    A write and a read, not a listing: a listing succeeds while writes still fail.
    """
    fs = s3fs_client()
    if fs.exists(bucket):
        state = "already present"
    else:
        fs.mkdir(bucket)
        # Some stores return from create before the bucket is listable, so confirm it.
        if not fs.exists(bucket):
            raise RuntimeError(f"created bucket {bucket} but it is not listable yet")
        state = "created"

    key = f"{bucket}/{PROBE_KEY}"
    fs.pipe(key, b"ready")
    if fs.cat(key) != b"ready":
        raise RuntimeError(f"round trip through {key} did not return what was written")
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=90.0, help="seconds to keep trying")
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between attempts")
    args = parser.parse_args()

    endpoint = require("S3_ENDPOINT")
    bucket = require("S3_BUCKET")
    deadline = time.monotonic() + args.timeout
    attempt = 0
    last_error = "no attempt was made"

    while time.monotonic() < deadline:
        attempt += 1
        try:
            state = probe(bucket)
            print(f"storage ready at {endpoint}, bucket {bucket} {state} (attempt {attempt})")
            return 0
        except Exception as error:  # s3fs and botocore raise several unrelated types here
            last_error = f"{type(error).__name__}: {str(error).splitlines()[0]}"
            print(f"  attempt {attempt}: {last_error}")
        time.sleep(args.interval)

    print(
        f"storage at {endpoint} did not become writable within {args.timeout:.0f}s\n"
        f"  last error: {last_error}\n"
        f"  check `docker compose ps` and the container logs",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
