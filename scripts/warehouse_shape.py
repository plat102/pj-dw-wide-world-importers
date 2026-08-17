#!/usr/bin/env python
"""Print every relation in the warehouse with its row and column count.

This exists so no document has to carry a row count. Counts change whenever the data span
changes, and a number copied into prose is a second source of truth that nobody updates.

    uv run python scripts/warehouse_shape.py       # or: make shape
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import duckdb

DEFAULT_DB = Path(__file__).resolve().parent.parent / "wwi.duckdb"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        default=os.environ.get("DUCKDB_PATH", str(DEFAULT_DB)),
        help="path to the DuckDB file (default: $DUCKDB_PATH, else wwi.duckdb)",
    )
    args = parser.parse_args()

    if not Path(args.database).exists():
        sys.exit(f"{args.database} does not exist -- run `make build` first")

    conn = duckdb.connect(args.database, read_only=True)

    columns = dict(
        conn.execute(
            "select table_schema || '.' || table_name, count(*) "
            "from information_schema.columns where table_schema like 'main_%' "
            "group by 1"
        ).fetchall()
    )
    if not columns:
        sys.exit(f"{args.database} holds no main_* schema -- was the build interrupted?")

    # Views have no stored row count, so they have to be counted. Build one union query
    # rather than a round trip per relation.
    counts_sql = conn.execute(
        "select string_agg("
        "  format('select ''{}.{}'' as relation, count(*) as rows from \"{}\".\"{}\"',"
        "         table_schema, table_name, table_schema, table_name),"
        "  ' union all ' order by table_schema, table_name)"
        " from information_schema.tables where table_schema like 'main_%'"
    ).fetchone()[0]
    rows = conn.execute(f"{counts_sql} order by relation").fetchall()

    width = max(len(name) for name, _ in rows)
    layer = None
    for name, count in rows:
        schema = name.split(".", 1)[0]
        if schema != layer:
            print(f"\n{schema}")
            layer = schema
        print(f"  {name:<{width}}  {count:>9,} rows  {columns[name]:>3} columns")

    print(f"\n{len(rows)} relations, {sum(columns.values())} columns total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
