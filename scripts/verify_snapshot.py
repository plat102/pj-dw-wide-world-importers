"""Check a downloaded snapshot against the committed manifest.

Needs no credential and no network. This is the whole point of the boundary: a
consumer decides whether the data is what it should be without trusting, or even
contacting, whoever produced it.

    python scripts/verify_snapshot.py --input-dir data/raw --manifest data/snapshots/manifest.json

Failures are reported separately because they have separate causes:

    missing file      the download is incomplete
    checksum          the file changed after publication
    row count         the file is not the one the manifest describes
    schema version    the source schema moved; models may not apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq
import yaml

CHUNK = 1024 * 1024
REPO_ROOT = Path(__file__).resolve().parent.parent
TABLES_CONFIG = REPO_ROOT / "etl" / "tables.yml"


def expected_schema_version() -> int:
    """The schema this checkout expects; read from tables.yml so there is one copy."""
    return yaml.safe_load(TABLES_CONFIG.read_text(encoding="utf-8"))["schema_version"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir", default="data/raw")
    p.add_argument("--manifest", default="data/snapshots/manifest.json")
    p.add_argument("--expect-schema-version", type=int, default=None)
    args = p.parse_args()
    expect = args.expect_schema_version
    if expect is None:
        expect = expected_schema_version()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"FAIL manifest: {manifest_path} not found", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    in_dir = Path(args.input_dir)

    failures: list[str] = []

    got = manifest.get("schema_version")
    if got != expect:
        failures.append(
            f"schema version: manifest says {got}, this checkout expects "
            f"{expect}; the source schema moved"
        )

    for name, spec in manifest["tables"].items():
        path = in_dir / spec["file"]
        if not path.exists():
            failures.append(f"missing file: {spec['file']} (download is incomplete)")
            continue
        digest = sha256(path)
        if digest != spec["sha256"]:
            failures.append(
                f"checksum: {spec['file']} changed after publication "
                f"(expected {spec['sha256'][:12]}..., got {digest[:12]}...)"
            )
            continue
        pf = pq.ParquetFile(path)
        rows = pf.metadata.num_rows
        if rows != spec["row_count"]:
            failures.append(
                f"row count: {spec['file']} has {rows:,} rows, manifest says {spec['row_count']:,}"
            )
            continue
        expected_cols = spec.get("columns")
        if expected_cols is not None:
            actual = {f.name: str(f.type) for f in pf.schema_arrow}
            gone = sorted(set(expected_cols) - set(actual))
            added = sorted(set(actual) - set(expected_cols))
            retyped = sorted(c for c in set(actual) & set(expected_cols) if actual[c] != expected_cols[c])
            if gone or added or retyped:
                parts = []
                if gone:
                    parts.append(f"missing {gone}")
                if added:
                    parts.append(f"unexpected {added}")
                if retyped:
                    parts.append(
                        "retyped " + ", ".join(f"{c} {expected_cols[c]}->{actual[c]}" for c in retyped)
                    )
                failures.append(f"column schema: {spec['file']} " + "; ".join(parts))

    extra = {p.name for p in in_dir.glob("*.parquet")} - {s["file"] for s in manifest["tables"].values()}
    for name in sorted(extra):
        failures.append(f"unexpected file: {name} is not in the manifest")

    if failures:
        for f in failures:
            print(f"FAIL {f}", file=sys.stderr)
        print(f"\n{len(failures)} check(s) failed", file=sys.stderr)
        return 1

    mb = manifest["total_size_bytes"] / 1048576
    print(
        f"OK {manifest['table_count']} tables, {manifest['total_row_count']:,} rows, {mb:.1f} MB\n"
        f"   snapshot {manifest['snapshot_timestamp']}, schema version {manifest['schema_version']}\n"
        f"   source {manifest['mssql_version']}\n"
        f"   delivery time captured as {manifest['delivery_time_form']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
