"""Check the published snapshot against the committed manifest, never touching the source.

Reports missing file, checksum, row count, column schema and schema version separately.

    python -m scripts.verify_snapshot       # or: make verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq
import yaml

from scripts.snapshot_layout import bronze_prefix
from scripts.warehouse import require, s3fs_client

REPO_ROOT = Path(__file__).resolve().parent.parent
TABLES_CONFIG = REPO_ROOT / "etl" / "tables.yml"
MANIFEST = REPO_ROOT / "data" / "snapshots" / "manifest.json"


def expected_schema_version() -> int:
    """The schema this checkout expects; read from tables.yml so there is one copy."""
    return yaml.safe_load(TABLES_CONFIG.read_text(encoding="utf-8"))["schema_version"]


class StoreSource:
    """The snapshot as objects on the store, under the manifest's own prefix."""

    def __init__(self, manifest: dict) -> None:
        self.bucket = require("S3_BUCKET")
        self.prefix = bronze_prefix(manifest)
        self.label = f"s3://{self.bucket}/{self.prefix}/"
        self.fs = s3fs_client()

    def _key(self, file_name: str) -> str:
        return f"{self.bucket}/{self.prefix}/{file_name}"

    def exists(self, file_name: str) -> bool:
        return self.fs.exists(self._key(file_name))

    def open(self, file_name: str):
        return self.fs.open(self._key(file_name), "rb")

    def list_parquet(self) -> set[str]:
        found = self.fs.find(f"{self.bucket}/{self.prefix}/")
        return {key.rsplit("/", 1)[-1] for key in found if key.endswith(".parquet")}


def sha256_stream(handle) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def check_table(source, spec: dict) -> str | None:
    """One table's four checks. Returns the first failure, or None when it passes."""
    if not source.exists(spec["file"]):
        return f"missing file: {spec['file']} (the snapshot is incomplete)"

    with source.open(spec["file"]) as handle:
        digest = sha256_stream(handle)
    if digest != spec["sha256"]:
        return (
            f"checksum: {spec['file']} changed after publication "
            f"(expected {spec['sha256'][:12]}..., got {digest[:12]}...)"
        )

    with source.open(spec["file"]) as handle:
        parquet = pq.ParquetFile(handle)
        arrow_schema = parquet.schema_arrow
        rows = parquet.metadata.num_rows
    if rows != spec["row_count"]:
        return f"row count: {spec['file']} has {rows:,} rows, manifest says {spec['row_count']:,}"

    expected = spec["columns"]
    actual = {field.name: str(field.type) for field in arrow_schema}
    gone = sorted(set(expected) - set(actual))
    added = sorted(set(actual) - set(expected))
    retyped = sorted(c for c in set(actual) & set(expected) if actual[c] != expected[c])
    if gone or added or retyped:
        parts = []
        if gone:
            parts.append(f"missing {gone}")
        if added:
            parts.append(f"unexpected {added}")
        if retyped:
            parts.append(
                "retyped " + ", ".join(f"{c} {expected[c]}->{actual[c]}" for c in retyped)
            )
        return f"column schema: {spec['file']} " + "; ".join(parts)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(MANIFEST))
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"FAIL manifest: {manifest_path} not found", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = StoreSource(manifest)

    failures: list[str] = []

    expect = expected_schema_version()
    if manifest.get("schema_version") != expect:
        failures.append(
            f"schema version: manifest says {manifest.get('schema_version')}, this checkout "
            f"expects {expect}; the source schema moved"
        )

    for spec in manifest["tables"].values():
        failure = check_table(source, spec)
        if failure:
            failures.append(failure)

    extra = source.list_parquet() - {s["file"] for s in manifest["tables"].values()}
    for name in sorted(extra):
        failures.append(f"unexpected file: {name} is not in the manifest")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        print(f"\n{len(failures)} check(s) failed", file=sys.stderr)
        return 1

    print(f"source: {source.label}")
    print(
        f"OK {manifest['table_count']} tables, {manifest['total_row_count']:,} rows, "
        f"{manifest['total_size_bytes'] / 1048576:.1f} MB\n"
        f"   snapshot {manifest['snapshot_timestamp']}, "
        f"schema version {manifest['schema_version']}\n"
        f"   source {manifest['mssql_version']}\n"
        f"   delivery time captured as {manifest['delivery_time_form']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
