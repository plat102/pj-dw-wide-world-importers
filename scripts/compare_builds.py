#!/usr/bin/env python
"""Build the warehouse twice and diff the two results using DuckLake time travel.

Names the table and column that differ. Views are skipped: they are re-evaluated on read.

    python -m scripts.compare_builds       # or: make compare
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from scripts.warehouse import connect

REPO_ROOT = Path(__file__).resolve().parent.parent
DBT_DIR = "wide_world_importers_dw"


def build(profiles_dir: str | None) -> None:
    command = ["dbt", "build", "--project-dir", f"./{DBT_DIR}"]
    if profiles_dir:
        command += ["--profiles-dir", profiles_dir]
    result = subprocess.run(
        command, cwd=REPO_ROOT, env=os.environ.copy(), capture_output=True, text=True
    )
    if result.returncode != 0:
        # Redacted: the attach string carries the catalog password and dbt echoes it on failure.
        sys.stdout.write(_redact(result.stdout[-4000:]))
        sys.exit("dbt build failed; see output above")


def _redact(text: str) -> str:
    return re.sub(r"password=\S+", "password=***", text)


def latest_snapshot(conn) -> int:
    return conn.execute("select max(snapshot_id) from ducklake_snapshots('lake')").fetchone()[0]


def tables(conn) -> list[tuple[str, str]]:
    return conn.execute(
        """
        select table_schema, table_name
        from information_schema.tables
        where table_catalog = 'lake' and table_type = 'BASE TABLE'
        order by table_schema, table_name
        """
    ).fetchall()


def columns(conn, schema: str, table: str) -> list[str]:
    return [
        row[0]
        for row in conn.execute(
            """
            select column_name from information_schema.columns
            where table_catalog = 'lake' and table_schema = ? and table_name = ?
            order by ordinal_position
            """,
            [schema, table],
        ).fetchall()
    ]


def column_report(conn, schema: str, table: str, first: int, second: int) -> str:
    """Name the columns that differ; a whole-row diff says how many rows, never which column."""
    names = columns(conn, schema, table)
    key = next((name for name in names if name.endswith("_key")), None)
    if key is None:
        return "no *_key column to align rows on; compare by hand"
    left = f'lake."{schema}"."{table}" at (version => {first})'
    right = f'lake."{schema}"."{table}" at (version => {second})'
    culprits = []
    for name in names:
        if name == key:
            continue
        mismatched = conn.execute(
            f'select count(*) from {left} a join {right} b using ("{key}") '
            f'where a."{name}" is distinct from b."{name}"'
        ).fetchone()[0]
        if mismatched:
            culprits.append(f"{name} ({mismatched:,} rows)")
    if not culprits:
        return "no column differs; the row counts do"
    return "columns differing: " + ", ".join(culprits)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles-dir", default=None, help="passed through to dbt")
    args = parser.parse_args()

    print("building twice into the lake; each build commits a snapshot")
    build(args.profiles_dir)
    conn = connect()
    first = latest_snapshot(conn)
    conn.close()

    build(args.profiles_dir)
    conn = connect()
    second = latest_snapshot(conn)

    if first == second:
        sys.exit(
            f"both builds report snapshot {first} -- nothing was committed, so there is "
            "nothing to compare"
        )
    print(f"comparing snapshot {first} against {second}\n")

    differing = []
    relations = tables(conn)
    for schema, table in relations:
        left = f'lake."{schema}"."{table}" at (version => {first})'
        right = f'lake."{schema}"."{table}" at (version => {second})'
        only_first = conn.execute(
            f"select count(*) from (select * from {left} except select * from {right})"
        ).fetchone()[0]
        only_second = conn.execute(
            f"select count(*) from (select * from {right} except select * from {left})"
        ).fetchone()[0]
        rows = conn.execute(f"select count(*) from {right}").fetchone()[0]
        status = "OK  " if not (only_first or only_second) else "DIFF"
        print(f"{status} {schema}.{table:<34} {rows:>9,} rows")
        if only_first or only_second:
            differing.append((schema, table, only_first, only_second, rows))

    print(f"\n{len(relations)} tables compared, {len(differing)} differing")
    for schema, table, only_first, only_second, rows in differing:
        print(
            f"  {schema}.{table}: {only_first} rows only in snapshot {first}, "
            f"{only_second} only in {second}, of {rows:,}"
        )
        print(f"    -> {column_report(conn, schema, table, first, second)}")

    if not differing:
        views = conn.execute(
            "select count(*) from information_schema.tables "
            "where table_catalog = 'lake' and table_type = 'VIEW'"
        ).fetchone()[0]
        print(f"({views} views not compared -- a view is re-evaluated on read)")

    return 1 if differing else 0


if __name__ == "__main__":
    raise SystemExit(main())
