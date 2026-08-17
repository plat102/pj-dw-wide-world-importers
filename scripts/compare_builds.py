#!/usr/bin/env python
"""Build the warehouse twice into separate DuckDB files and diff every relation.

Two builds of one snapshot must produce identical output. Anything that differs is a
non-determinism -- a clock, an unordered aggregate, a hash seed -- and the point of this
script is to name which relation and how many rows, not just to fail.

    uv run python scripts/compare_builds.py

Exits 0 when every relation matches, 1 otherwise.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
DBT_DIR = "wide_world_importers_dw"


def build(db_path: Path, profiles_dir: str | None) -> None:
    """Run dbt build into db_path. DUCKDB_PATH is what the profile reads."""
    cmd = ["dbt", "build", "--project-dir", f"./{DBT_DIR}"]
    if profiles_dir:
        cmd += ["--profiles-dir", profiles_dir]
    env = {**os.environ, "DUCKDB_PATH": str(db_path)}
    result = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stdout.write(result.stdout[-4000:])
        sys.exit(f"dbt build failed for {db_path.name}; see output above")


def compare(first: Path, second: Path) -> int:
    # Attach under the file stem so views, which store catalog-qualified references,
    # still resolve. Attaching under an alias breaks every view in the database.
    conn = duckdb.connect()
    conn.execute(f"attach '{first}' as {first.stem} (read_only)")
    conn.execute(f"attach '{second}' as {second.stem} (read_only)")

    relations = conn.execute(
        "select table_schema, table_name from information_schema.tables "
        "where table_catalog = ? and table_schema like 'main_%' "
        "order by table_schema, table_name",
        [first.stem],
    ).fetchall()
    if not relations:
        sys.exit("no relations found -- did the build write to the expected database?")

    differing = []
    for schema, table in relations:
        left = f'{first.stem}."{schema}"."{table}"'
        right = f'{second.stem}."{schema}"."{table}"'
        only_first = conn.execute(
            f"select count(*) from (select * from {left} except select * from {right})"
        ).fetchone()[0]
        only_second = conn.execute(
            f"select count(*) from (select * from {right} except select * from {left})"
        ).fetchone()[0]
        rows = conn.execute(f"select count(*) from {left}").fetchone()[0]
        status = "OK  " if not (only_first or only_second) else "DIFF"
        print(f"{status} {schema}.{table:<34} {rows:>9,} rows")
        if only_first or only_second:
            differing.append((f"{schema}.{table}", only_first, only_second, rows))

    print(f"\n{len(relations)} relations compared, {len(differing)} differing")
    for name, only_first, only_second, rows in differing:
        print(f"  {name}: {only_first} rows only in the first build, "
              f"{only_second} only in the second, of {rows:,}")
        print(f"    -> {column_report(conn, first.stem, second.stem, name)}")
    return 1 if differing else 0


def column_report(conn, first: str, second: str, qualified: str) -> str:
    """Name the columns that actually differ; a whole-row diff never says which."""
    schema, table = qualified.split(".", 1)
    columns = [
        r[0]
        for r in conn.execute(
            "select column_name from information_schema.columns "
            "where table_catalog = ? and table_schema = ? and table_name = ? "
            "order by ordinal_position",
            [first, schema, table],
        ).fetchall()
    ]
    # Without a key there is nothing to join on, so fall back to per-column distinct counts.
    key = next((c for c in columns if c.endswith("_key")), None)
    if key is None:
        return "no *_key column to align rows on; compare by hand"
    culprits = []
    for column in columns:
        if column == key:
            continue
        mismatched = conn.execute(
            f'select count(*) from {first}."{schema}"."{table}" a '
            f'join {second}."{schema}"."{table}" b using ("{key}") '
            f'where a."{column}" is distinct from b."{column}"'
        ).fetchone()[0]
        if mismatched:
            culprits.append(f"{column} ({mismatched:,} rows)")
    return "columns differing: " + (", ".join(culprits) if culprits else "none; row counts differ instead")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles-dir", default=None, help="passed through to dbt")
    parser.add_argument("--keep", action="store_true", help="do not delete the two databases")
    args = parser.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="wwi-compare-"))
    first, second = workdir / "first.duckdb", workdir / "second.duckdb"
    print(f"building twice into {workdir}")
    build(first, args.profiles_dir)
    build(second, args.profiles_dir)
    code = compare(first, second)
    if args.keep:
        print(f"\ndatabases kept at {workdir}")
    else:
        for path in workdir.glob("*.duckdb*"):
            path.unlink()
        workdir.rmdir()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
