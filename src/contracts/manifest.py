"""Read, write and describe the snapshot manifest.

The manifest is committed and the Parquet it describes is not, so it is the only thing downstream
can check the snapshot against. Row counts, sizes and per-column Arrow types are all part of the
contract, not just the checksums.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from contracts.paths import snapshot_id
from utils.checksums import sha256_file
from utils.exceptions import ToolingError


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ToolingError(f"{path} does not exist -- run `make extract` first")
    return json.loads(path.read_text(encoding="utf-8"))


def dump(manifest: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def describe_file(path: Path) -> dict[str, Any]:
    """One table's entry. The contract is the columns and their types, not only the bytes."""
    parquet = pq.ParquetFile(path)
    return {
        "file": path.name,
        "row_count": parquet.metadata.num_rows,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "columns": {f.name: str(f.type) for f in parquet.schema_arrow},
    }


def summarise(tables: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "table_count": len(tables),
        "total_size_bytes": sum(t["size_bytes"] for t in tables.values()),
        "total_row_count": sum(t["row_count"] for t in tables.values()),
    }


def build(extraction: dict[str, Any], tables: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Assemble the manifest from what the extraction reported and what is on disk."""
    return {
        "schema_version": extraction["schema_version"],
        "snapshot_timestamp": extraction["load_timestamp"],
        # Written out rather than left to each consumer to re-derive, so the layout format has
        # exactly one definition -- contracts/paths.py.
        "snapshot_id": snapshot_id(extraction["load_timestamp"]),
        "mssql_version": extraction["mssql_version"],
        "delivery_time_form": extraction["delivery_time_form"],
        **summarise(tables),
        "tables": tables,
    }


def assert_matches_extraction(extraction: dict[str, Any], tables: dict[str, dict]) -> None:
    """The extraction is the authority on what it wrote; never describe a remainder as the whole."""
    expected = extraction["files"]
    if set(expected) != set(tables):
        only_extraction = sorted(set(expected) - set(tables))
        only_disk = sorted(set(tables) - set(expected))
        raise ToolingError(
            "data/raw no longer matches the extraction: "
            f"missing {only_extraction or 'none'}, unexpected {only_disk or 'none'}"
        )
    mismatched = [n for n in expected if expected[n] != tables[n]["row_count"]]
    if mismatched:
        detail = ", ".join(
            f"{n}: extraction {expected[n]:,} vs file {tables[n]['row_count']:,}"
            for n in mismatched
        )
        raise ToolingError(f"row counts changed since the extraction: {detail}")


def generate(input_dir: Path, output: Path) -> str:
    """Describe every Parquet file in `input_dir` and write the manifest. Returns a summary line."""
    extraction_file = input_dir / "_extraction.json"
    if not extraction_file.exists():
        raise ToolingError(f"{extraction_file} is missing -- run the extraction first")
    extraction = json.loads(extraction_file.read_text(encoding="utf-8"))

    files = sorted(input_dir.glob("*.parquet"))
    if not files:
        raise ToolingError(f"no parquet files in {input_dir}")

    tables = {path.stem: describe_file(path) for path in files}
    assert_matches_extraction(extraction, tables)

    manifest = build(extraction, tables)
    dump(manifest, output)
    mb = manifest["total_size_bytes"] / 1048576
    return f"{output}: {len(tables)} tables, {manifest['total_row_count']:,} rows, {mb:.1f} MB"
