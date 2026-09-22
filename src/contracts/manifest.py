"""Read, write and describe the snapshot manifest.

The manifest is committed and the Parquet it describes is not, so it is the only thing downstream
can check the snapshot against. A table is one or more Parquet files under its own folder -- dlt
decides how many -- so `files` is a list and the table's row count is their sum.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, BinaryIO

import pyarrow.parquet as pq

from utils.checksums import sha256_stream
from utils.exceptions import ToolingError


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ToolingError(f"{path} does not exist -- run `make extract` first")
    return json.loads(path.read_text(encoding="utf-8"))


def dump(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _read_parquet(handle: BinaryIO) -> tuple[int, dict[str, str]]:
    parquet = pq.ParquetFile(handle)
    return parquet.metadata.num_rows, {f.name: str(f.type) for f in parquet.schema_arrow}


def describe_stored(fs: Any, bucket: str, prefix: str, key: str) -> dict[str, Any]:
    """One file, read back off the store, so the checksum covers the bytes that were published."""
    full = f"{bucket}/{prefix}/{key}"
    with fs.open(full, "rb") as handle:
        rows, columns = _read_parquet(handle)
    with fs.open(full, "rb") as handle:
        digest = sha256_stream(handle)
    return {
        "file": key,
        "row_count": rows,
        "size_bytes": int(fs.info(full)["size"]),
        "sha256": digest,
        "columns": columns,
    }


def collect(files: list[dict[str, Any]]) -> dict[str, Any]:
    """Fold a table's files into its manifest entry. Every file must carry the same columns."""
    columns = files[0]["columns"]
    drifted = [f["file"] for f in files if f["columns"] != columns]
    if drifted:
        raise ToolingError(
            f"one table was written with more than one column schema: {', '.join(drifted)}"
        )
    return {
        "row_count": sum(f["row_count"] for f in files),
        "size_bytes": sum(f["size_bytes"] for f in files),
        "columns": columns,
        "files": [
            {"file": f["file"], "size_bytes": f["size_bytes"], "sha256": f["sha256"]}
            for f in sorted(files, key=lambda f: f["file"])
        ],
    }


def from_store(fs: Any, bucket: str, prefix: str, expected: list[str]) -> dict[str, dict[str, Any]]:
    """Describe every Parquet under the prefix, grouped into the table folder it sits in."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for full in fs.find(f"{bucket}/{prefix}/"):
        key = full.split(f"{prefix}/", 1)[-1]
        if not key.endswith(".parquet"):
            continue
        # `<table>/<file>.parquet` -- the folder is the table, whatever dlt named the file.
        table = key.split("/", 1)[0]
        grouped.setdefault(table, []).append(describe_stored(fs, bucket, prefix, key))

    missing = sorted(set(expected) - set(grouped))
    if missing:
        raise ToolingError(f"nothing landed for {len(missing)} table(s): {', '.join(missing)}")
    empty = sorted(n for n, files in grouped.items() if sum(f["row_count"] for f in files) == 0)
    if empty:
        raise ToolingError(f"{', '.join(empty)} landed with no rows; every table must carry data")
    return {name: collect(grouped[name]) for name in sorted(grouped)}


def summarise(tables: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "table_count": len(tables),
        "total_size_bytes": sum(t["size_bytes"] for t in tables.values()),
        "total_row_count": sum(t["row_count"] for t in tables.values()),
    }
