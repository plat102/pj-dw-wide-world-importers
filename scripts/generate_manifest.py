"""Describe a Parquet snapshot completely enough that a consumer can verify it later.

Source facts come from data/raw/_extraction.json. The manifest is committed; the Parquet is not.

    python -m scripts.generate_manifest       # or: make manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

from scripts.snapshot_layout import snapshot_id

CHUNK = 1024 * 1024


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir", default="data/raw")
    p.add_argument("--output", default="data/snapshots/manifest.json")
    args = p.parse_args()

    in_dir = Path(args.input_dir)
    extraction_file = in_dir / "_extraction.json"
    if not extraction_file.exists():
        sys.exit(f"{extraction_file} is missing -- run the extraction first")
    extraction = json.loads(extraction_file.read_text(encoding="utf-8"))

    files = sorted(in_dir.glob("*.parquet"))
    if not files:
        sys.exit(f"no parquet files in {in_dir}")

    tables = {}
    for path in files:
        pf = pq.ParquetFile(path)
        tables[path.stem] = {
            "file": path.name,
            "row_count": pf.metadata.num_rows,
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            # The contract is the columns and types, not just the bytes.
            "columns": {f.name: str(f.type) for f in pf.schema_arrow},
        }

    # The extraction is the authority on what it wrote; never describe a remainder as the whole.
    expected = extraction["files"]
    if set(expected) != set(tables):
        only_extraction = sorted(set(expected) - set(tables))
        only_disk = sorted(set(tables) - set(expected))
        sys.exit(
            "data/raw no longer matches the extraction: "
            f"missing {only_extraction or 'none'}, unexpected {only_disk or 'none'}"
        )
    mismatched = [n for n in expected if expected[n] != tables[n]["row_count"]]
    if mismatched:
        detail = ", ".join(
            f"{n}: extraction {expected[n]:,} vs file {tables[n]['row_count']:,}"
            for n in mismatched
        )
        sys.exit(f"row counts changed since the extraction: {detail}")

    manifest = {
        "schema_version": extraction["schema_version"],
        "snapshot_timestamp": extraction["load_timestamp"],
        # Written out rather than left to each consumer to re-derive, so the layout format has
        # exactly one definition -- scripts/snapshot_layout.py.
        "snapshot_id": snapshot_id(extraction["load_timestamp"]),
        "mssql_version": extraction["mssql_version"],
        "delivery_time_form": extraction["delivery_time_form"],
        "table_count": len(tables),
        "total_size_bytes": sum(t["size_bytes"] for t in tables.values()),
        "total_row_count": sum(t["row_count"] for t in tables.values()),
        "tables": tables,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    mb = manifest["total_size_bytes"] / 1048576
    print(f"{out}: {len(tables)} tables, {manifest['total_row_count']:,} rows, {mb:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
