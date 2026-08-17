#!/usr/bin/env python
"""Regenerate models/sources.yml from the snapshot manifest.

The manifest is authoritative for column names and types. This projects it into the shape dbt
wants, so the two can never disagree about what the snapshot contains.

Deliberately writes **no row counts, sizes or checksums**. Those are in the manifest, they change
with every extraction, and a copy in a second file is a copy that goes stale.

    uv run python scripts/generate_sources.py       # or: make sources
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "data" / "snapshots" / "manifest.json"
SOURCES = REPO_ROOT / "wide_world_importers_dw" / "models" / "sources.yml"

HEADER = """# GENERATED -- do not hand-edit. Regenerate with `make sources` after a new extraction.
# The manifest is authoritative for column names and types; this file is a projection of it.
version: 2
sources:
  - name: wwi_raw
    description: >
      Wide World Importers OLTP, frozen as a Parquet snapshot on the object store. Row counts,
      sizes and checksums live in data/snapshots/manifest.json, which is authoritative; they are
      not repeated here.
    meta:
      # The snapshot is addressed as s3:// in every environment. Only the endpoint and the
      # credentials differ between a laptop, CI and a real cloud bucket -- and those live in the
      # dbt profile, not here. Nothing in this file names the store behind the API.
      external_location: "read_parquet('s3://{{ env_var('S3_BUCKET', 'wwi') }}/bronze/{name}.parquet')"
    tables:
"""

# The manifest records Arrow types, because that is what the extraction sees. dbt wants the
# warehouse's own type names. Verified column by column against `describe select * from
# read_parquet(...)` across every table in the snapshot -- no Arrow type maps to two DuckDB types.
ARROW_TO_DUCKDB = {
    "bool": "BOOLEAN",
    "date32[day]": "DATE",
    "decimal128(18, 2)": "DECIMAL(18,2)",
    "decimal128(18, 3)": "DECIMAL(18,3)",
    "int64": "BIGINT",
    "string": "VARCHAR",
    "timestamp[us]": "TIMESTAMP",
}


def duckdb_type(arrow: str) -> str:
    """Fail loudly on an unmapped type rather than guessing or passing it through.

    A new Arrow type means the snapshot gained a column shape nobody has checked against DuckDB.
    Silently emitting the Arrow name would give dbt a type it does not know, and the error would
    surface far from its cause.
    """
    try:
        return ARROW_TO_DUCKDB[arrow]
    except KeyError:
        sys.exit(
            f"no DuckDB type mapped for Arrow type {arrow!r}. Add it to ARROW_TO_DUCKDB after "
            "confirming what `describe select * from read_parquet(...)` reports for that column."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(MANIFEST))
    parser.add_argument("--output", default=str(SOURCES))
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the output would differ, without writing. For CI.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        sys.exit(f"{manifest_path} does not exist -- run `make extract` first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    lines = [HEADER]
    for table in sorted(manifest["tables"]):
        lines.append(f"      - name: {table}\n")
        lines.append("        columns:\n")
        for column, arrow in manifest["tables"][table]["columns"].items():
            lines.append(f"          - name: {column}\n")
            lines.append(f"            data_type: {duckdb_type(arrow)}\n")
    rendered = "".join(lines)

    output = Path(args.output)
    if args.check:
        current = output.read_text(encoding="utf-8") if output.exists() else ""
        if current != rendered:
            sys.exit(
                f"{output.name} does not match the manifest -- run `make sources` and commit "
                "the result"
            )
        print(f"{output.name} matches the manifest")
        return 0

    output.write_text(rendered, encoding="utf-8")
    tables = len(manifest["tables"])
    columns = sum(len(t["columns"]) for t in manifest["tables"].values())
    print(f"wrote {output.relative_to(REPO_ROOT)}: {tables} tables, {columns} columns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
