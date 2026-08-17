#!/usr/bin/env python
"""Upload the local Parquet snapshot to the object store's bronze layer.

Needed because extraction still writes to `data/raw/` -- that moves to the store separately, and
this exists so the rest of the pipeline does not wait on it. It is also what CI will use to put a
snapshot in front of a build without touching SQL Server.

Verifies against `data/snapshots/manifest.json` on both sides: it refuses to upload a local file
whose SHA256 does not match, and re-reads each object afterwards to confirm what landed. A count
of uploaded files proves nothing about their contents.

    uv run python scripts/seed_bronze.py         # or: make seed_bronze

Exits 0 when every table in the manifest is present and correct on the store.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import s3fs

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "data" / "snapshots" / "manifest.json"
RAW_DIR = REPO_ROOT / "data" / "raw"


def sha256(path_or_bytes) -> str:
    digest = hashlib.sha256()
    if isinstance(path_or_bytes, bytes):
        digest.update(path_or_bytes)
        return digest.hexdigest()
    with open(path_or_bytes, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"{name} is not set -- copy .env.example to .env and fill it in")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default="bronze", help="key prefix inside the bucket")
    parser.add_argument("--manifest", default=str(MANIFEST))
    parser.add_argument("--raw-dir", default=str(RAW_DIR))
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify what is already on the store; upload nothing",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        sys.exit(f"{manifest_path} does not exist -- run `make extract` first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    endpoint = require("S3_ENDPOINT")
    bucket = require("S3_BUCKET")
    use_ssl = os.environ.get("S3_USE_SSL", "false").strip().lower() in {"1", "true", "yes"}
    scheme = "https" if use_ssl else "http"

    fs = s3fs.S3FileSystem(
        key=require("S3_ACCESS_KEY"),
        secret=require("S3_SECRET_KEY"),
        client_kwargs={"endpoint_url": f"{scheme}://{endpoint}"},
        # Path style, not virtual-host style: a local store has no per-bucket DNS.
        config_kwargs={"s3": {"addressing_style": "path"}},
    )

    raw_dir = Path(args.raw_dir)
    problems: list[str] = []
    uploaded = 0

    for table, entry in sorted(manifest["tables"].items()):
        expected = entry["sha256"]
        key = f"{bucket}/{args.prefix}/{entry['file']}"

        if not args.check:
            local = raw_dir / entry["file"]
            if not local.exists():
                problems.append(f"{table}: {local} is missing locally")
                continue
            actual = sha256(local)
            if actual != expected:
                # Uploading it would put a file on the store that the manifest disowns.
                problems.append(
                    f"{table}: local checksum {actual[:12]} does not match manifest "
                    f"{expected[:12]} -- refusing to upload"
                )
                continue
            fs.put_file(str(local), key)
            uploaded += 1

        # Read back from the store, whether we just wrote it or not.
        if not fs.exists(key):
            problems.append(f"{table}: not present on the store at s3://{key}")
            continue
        with fs.open(key, "rb") as handle:
            remote = sha256(handle.read())
        if remote != expected:
            problems.append(
                f"{table}: object checksum {remote[:12]} does not match manifest {expected[:12]}"
            )

    verb = "verified" if args.check else "uploaded and verified"
    total = len(manifest["tables"])
    if problems:
        print(f"{len(problems)} problem(s) across {total} tables:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(f"{verb} {total} tables under s3://{bucket}/{args.prefix}/", end="")
    print(f" ({uploaded} uploaded)" if uploaded else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
