"""Check the published snapshot against the committed manifest, never touching the source.

Missing file, checksum, row count, column schema and schema version are reported separately: a
consumer that only learns "it failed" cannot tell a truncated upload from a moved source schema.
"""

from __future__ import annotations

from typing import Any, BinaryIO

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
        self.prefix = bronze_prefix(manifest)
        self.label = f"s3://{self.bucket}/{self.prefix}/"
        self.fs = s3.client()

    def _key(self, file_name: str) -> str:
        return f"{self.bucket}/{self.prefix}/{file_name}"

    def exists(self, file_name: str) -> bool:
        return bool(self.fs.exists(self._key(file_name)))

    def open(self, file_name: str) -> BinaryIO:
        return self.fs.open(self._key(file_name), "rb")

    def list_parquet(self) -> set[str]:
        found = self.fs.find(f"{self.bucket}/{self.prefix}/")
        return {key.rsplit("/", 1)[-1] for key in found if key.endswith(".parquet")}


def check_table(source: Any, spec: dict) -> str | None:
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
            parts.append("retyped " + ", ".join(f"{c} {expected[c]}->{actual[c]}" for c in retyped))
        return f"column schema: {spec['file']} " + "; ".join(parts)
    return None


def failures(manifest: dict, source: Any) -> list[str]:
    """Every check, collected rather than short-circuited: one run should name every problem."""
    found: list[str] = []

    expect = tables_contract.schema_version()
    if manifest.get("schema_version") != expect:
        found.append(
            f"schema version: manifest says {manifest.get('schema_version')}, this checkout "
            f"expects {expect}; the source schema moved"
        )

    for spec in manifest["tables"].values():
        failure = check_table(source, spec)
        if failure:
            found.append(failure)

    extra = source.list_parquet() - {s["file"] for s in manifest["tables"].values()}
    found.extend(f"unexpected file: {name} is not in the manifest" for name in sorted(extra))
    return found


def summary(manifest: dict, source: Any) -> str:
    return (
        f"source: {source.label}\n"
        f"OK {manifest['table_count']} tables, {manifest['total_row_count']:,} rows, "
        f"{manifest['total_size_bytes'] / 1048576:.1f} MB\n"
        f"   snapshot {manifest['snapshot_timestamp']}, "
        f"schema version {manifest['schema_version']}\n"
        f"   source {manifest['mssql_version']}\n"
        f"   delivery time captured as {manifest['delivery_time_form']}"
    )
