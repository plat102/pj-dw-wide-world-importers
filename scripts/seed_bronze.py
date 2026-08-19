#!/usr/bin/env python
"""Publish the local Parquet snapshot to the object store's bronze layer.

Refuses any file whose SHA256 disagrees with the manifest. `--empty` seeds schema only, for CI.

    python -m scripts.seed_bronze            # or: make seed_bronze
    python -m scripts.seed_bronze --empty    # or: make seed_bronze_empty
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from scripts.generate_sources import ARROW_TO_DUCKDB
from scripts.snapshot_layout import bronze_prefix
from scripts.warehouse import require, s3fs_client, store_connection

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "data" / "snapshots" / "manifest.json"
RAW_DIR = REPO_ROOT / "data" / "raw"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def published_snapshot_present(fs, bucket: str, prefix: str, manifest: dict) -> bool:
    """True when the real snapshot already occupies these keys: one listing against its sizes."""
    sizes = {
        key.rsplit("/", 1)[-1]: info["size"]
        for key, info in fs.find(f"{bucket}/{prefix}/", detail=True).items()
    }
    return all(
        sizes.get(entry["file"]) == entry["size_bytes"] for entry in manifest["tables"].values()
    )


def seed_empty(manifest: dict, bucket: str, prefix: str) -> list[str]:
    """Write zero-row Parquet carrying the manifest's columns and types.

    Checks the schema, not the checksum: an empty file is a different artifact by design.
    """
    conn = store_connection()
    problems: list[str] = []

    for table, entry in sorted(manifest["tables"].items()):
        target = f"s3://{bucket}/{prefix}/{entry['file']}"
        columns = entry["columns"]
        try:
            selected = ", ".join(
                f'cast(null as {ARROW_TO_DUCKDB[arrow]}) as "{name}"'
                for name, arrow in columns.items()
            )
        except KeyError as missing:
            problems.append(f"{table}: no DuckDB type mapped for Arrow type {missing}")
            continue
        # `where false` gives the right schema and no rows.
        conn.execute(f"copy (select {selected} where false) to '{target}' (format parquet)")

        described = conn.execute(f"describe select * from read_parquet('{target}')").fetchall()
        actual = {name: kind for name, kind, *_ in described}
        expected = {name: ARROW_TO_DUCKDB[arrow] for name, arrow in columns.items()}
        if actual != expected:
            retyped = [
                f"{c}: {expected[c]} -> {actual[c]}"
                for c in expected
                if c in actual and actual[c] != expected[c]
            ]
            problems.append(
                f"{table}: written schema disagrees with the manifest -- "
                f"missing {[c for c in expected if c not in actual]}, "
                f"extra {[c for c in actual if c not in expected]}, retyped {retyped}"
            )
        rows = conn.execute(f"select count(*) from read_parquet('{target}')").fetchone()[0]
        if rows:
            problems.append(f"{table}: expected zero rows, got {rows}")
    return problems


def upload(manifest: dict, fs, bucket: str, prefix: str, data_dir: Path) -> list[str]:
    problems: list[str] = []
    for table, entry in sorted(manifest["tables"].items()):
        local = data_dir / entry["file"]
        if not local.exists():
            problems.append(f"{table}: {local} is missing locally")
            continue
        actual = sha256(local)
        if actual != entry["sha256"]:
            # Uploading it would put a file on the store that the manifest disowns.
            problems.append(
                f"{table}: local checksum {actual[:12]} does not match manifest "
                f"{entry['sha256'][:12]} -- refusing to upload"
            )
            continue
        fs.put_file(str(local), f"{bucket}/{prefix}/{entry['file']}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--empty",
        action="store_true",
        help="write zero-row Parquet with the manifest's schema instead of uploading data (CI)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="with --empty, overwrite a published snapshot that is already on the store",
    )
    # A manifest and the Parquet it describes are passed separately because they do not live
    # together: the snapshot's manifest is committed while its Parquet is not, so they sit in
    # different directories. The demo fixture keeps both in one place; neither path is special-cased.
    parser.add_argument("--manifest", default=str(MANIFEST))
    parser.add_argument("--data-dir", default=str(RAW_DIR))
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    data_dir = Path(args.data_dir)
    if not manifest_path.exists():
        sys.exit(f"{manifest_path} does not exist -- run `make extract` first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    bucket = require("S3_BUCKET")
    fs = s3fs_client()
    # <prefix>/<snapshot-id>, so a new extraction lands beside the previous one. The contract
    # requires a new identifier, not a replaced file.
    prefix = bronze_prefix(manifest)
    total = len(manifest["tables"])

    if args.empty:
        # sources.yml names this prefix, so an empty seed writes the keys the real snapshot holds.
        if not args.force and published_snapshot_present(fs, bucket, prefix, manifest):
            sys.exit(
                f"s3://{bucket}/{prefix}/ already holds the published snapshot -- refusing to "
                "replace it with empty files. Pass --force if that is really what you want"
            )
        problems = seed_empty(manifest, bucket, prefix)
        verb = f"wrote {total} zero-row tables"
    else:
        problems = upload(manifest, fs, bucket, prefix, data_dir)
        verb = f"uploaded {total} tables"

    if problems:
        print(f"{len(problems)} problem(s) across {total} tables:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print(f"{verb} to s3://{bucket}/{prefix}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
