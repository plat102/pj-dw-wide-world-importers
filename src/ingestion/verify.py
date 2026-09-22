"""Check the published snapshot against the committed manifest, never touching the source.

Missing file, checksum, row count, column schema and schema version are reported separately: a
consumer that only learns "it failed" cannot tell a truncated upload from a moved source schema.
"""

from __future__ import annotations

from typing import BinaryIO

import pyarrow.parquet as pq

from config import settings
from connectors import s3
from contracts import tables as tables_contract
from contracts.paths import bronze_prefix
from utils.checksums import sha256_stream


class StoreSource:
    """The snapshot as objects on the store, under the manifest's own prefix."""

    def __init__(self, manifest: dict) -> None:
        self.bucket = settings.bucket()
        self.prefix = bronze_prefix(manifest["snapshot_id"])
        self.label = f"s3://{self.bucket}/{self.prefix}/"
        self.fs = s3.client()

    def _key(self, key: str) -> str:
        return f"{self.bucket}/{self.prefix}/{key}"

    def exists(self, key: str) -> bool:
        return bool(self.fs.exists(self._key(key)))

    def open(self, key: str) -> BinaryIO:
        return self.fs.open(self._key(key), "rb")

    def list_parquet(self) -> set[str]:
        found = self.fs.find(f"{self.bucket}/{self.prefix}/")
        return {key.split(f"{self.prefix}/", 1)[-1] for key in found if key.endswith(".parquet")}


def check_table(source: StoreSource, table: str, entry: dict) -> list[str]:
    """One table's checks across however many files it was written as."""
    found: list[str] = []
    rows = 0
    columns: dict[str, str] = {}

    for spec in entry["files"]:
        key = spec["file"]
        if not source.exists(key):
            found.append(f"missing file: {key} (the snapshot is incomplete)")
            continue

        with source.open(key) as handle:
            digest = sha256_stream(handle)
        if digest != spec["sha256"]:
            found.append(
                f"checksum: {key} changed after publication "
                f"(expected {spec['sha256'][:12]}..., got {digest[:12]}...)"
            )
            continue

        with source.open(key) as handle:
            parquet = pq.ParquetFile(handle)
            columns = {field.name: str(field.type) for field in parquet.schema_arrow}
            rows += parquet.metadata.num_rows

    if found:
        return found

    if rows != entry["row_count"]:
        found.append(f"row count: {table} has {rows:,} rows, manifest says {entry['row_count']:,}")

    expected = entry["columns"]
    gone = sorted(set(expected) - set(columns))
    added = sorted(set(columns) - set(expected))
    retyped = sorted(c for c in set(columns) & set(expected) if columns[c] != expected[c])
    if gone or added or retyped:
        parts = []
        if gone:
            parts.append(f"missing {gone}")
        if added:
            parts.append(f"unexpected {added}")
        if retyped:
            moved = ", ".join(f"{c} {expected[c]}->{columns[c]}" for c in retyped)
            parts.append(f"retyped {moved}")
        found.append(f"column schema: {table} " + "; ".join(parts))
    return found


def failures(manifest: dict, source: StoreSource) -> list[str]:
    """Every check, collected rather than short-circuited: one run should name every problem."""
    found: list[str] = []

    expect = tables_contract.schema_version()
    if manifest.get("schema_version") != expect:
        found.append(
            f"schema version: manifest says {manifest.get('schema_version')}, this checkout "
            f"expects {expect}; the source schema moved"
        )

    declared: set[str] = set()
    for table, entry in sorted(manifest["tables"].items()):
        found.extend(check_table(source, table, entry))
        declared.update(spec["file"] for spec in entry["files"])

    extra = source.list_parquet() - declared
    found.extend(f"unexpected file: {name} is not in the manifest" for name in sorted(extra))
    return found


def summary(manifest: dict, source: StoreSource) -> str:
    return (
        f"source: {source.label}\n"
        f"OK {manifest['table_count']} tables, {manifest['total_row_count']:,} rows, "
        f"{manifest['total_size_bytes'] / 1048576:.1f} MB\n"
        f"   snapshot {manifest['snapshot_timestamp']}, "
        f"schema version {manifest['schema_version']}\n"
        f"   source {manifest['mssql_version']}\n"
        f"   delivery time captured as {manifest['delivery_time_form']}"
    )
