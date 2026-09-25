"""Two builds of one raw load must produce identical tables.

Needs the stack up and a loaded raw schema; `make test` skips it when either is missing.
Views are not compared: a view is re-evaluated on read, so two builds cannot disagree about one.
Raw is not compared either: dbt never rewrites it, so the answer is a foregone conclusion.
"""

from __future__ import annotations

import os
import subprocess

import duckdb
import pytest

from config import settings
from connectors import ducklake, s3

pytestmark = pytest.mark.integration


def _build() -> None:
    # check=False: a failed build is reported with dbt's own output, which says which node broke.
    result = subprocess.run(
        ["dbt", "build", "--project-dir", str(settings.DBT_DIR)],
        cwd=settings.REPO_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"dbt build failed:\n{result.stdout[-4000:]}")


def _columns(conn: duckdb.DuckDBPyConnection, schema: str, table: str) -> list[str]:
    return [
        row[0]
        for row in conn.execute(
            "select column_name from information_schema.columns "
            f"where table_catalog = '{ducklake.CATALOG}' and table_schema = ? and table_name = ? "
            "order by ordinal_position",
            [schema, table],
        ).fetchall()
    ]


def _column_report(
    conn: duckdb.DuckDBPyConnection, schema: str, table: str, first: int, second: int
) -> str:
    """Name the columns that differ; a whole-row diff says how many rows, never which column."""
    names = _columns(conn, schema, table)
    key = next((name for name in names if name.endswith("_key")), None)
    if key is None:
        return "no *_key column to align rows on; compare by hand"
    left = f'{ducklake.CATALOG}."{schema}"."{table}" at (version => {first})'
    right = f'{ducklake.CATALOG}."{schema}"."{table}" at (version => {second})'
    culprits = []
    for name in names:
        if name == key:
            continue
        mismatched = s3.scalar(
            conn,
            f'select count(*) from {left} a join {right} b using ("{key}") '
            f'where a."{name}" is distinct from b."{name}"',
        )
        if mismatched:
            culprits.append(f"{name} ({mismatched:,} rows)")
    return "columns differing: " + ", ".join(culprits) if culprits else "no column differs"


@pytest.fixture(scope="module")
def two_builds() -> tuple[duckdb.DuckDBPyConnection, int, int]:
    """Build twice; each build commits a lake snapshot that time travel can address."""
    try:
        conn = ducklake.connect()
    except Exception as error:
        pytest.skip(f"lake unreachable: {type(error).__name__}: {error}")

    # A reachable lake with an empty raw is "not set up", not a failure: the build would error
    # on every staging model and report it as non-determinism.
    raw = [t for s, t, _ in ducklake.relations(conn) if s == settings.RAW_SCHEMA]
    conn.close()
    if not raw:
        pytest.skip(f"{ducklake.CATALOG}.{settings.RAW_SCHEMA} is empty -- run `make extract`")

    _build()
    conn = ducklake.connect()
    first = ducklake.latest_snapshot(conn)
    conn.close()

    _build()
    conn = ducklake.connect()
    second = ducklake.latest_snapshot(conn)
    if first == second:
        pytest.fail(
            f"both builds report snapshot {first} -- nothing was committed, so there is nothing "
            "to compare"
        )
    return conn, first, second


def test_every_table_is_identical_across_two_builds(
    two_builds: tuple[duckdb.DuckDBPyConnection, int, int],
) -> None:
    conn, first, second = two_builds
    relations = [
        (s, t)
        for s, t, _ in ducklake.relations(conn, table_type="BASE TABLE")
        if s != settings.RAW_SCHEMA
    ]
    assert relations, "the lake holds no built tables -- run `make build` first"

    differing = []
    for schema, table in relations:
        left = f'{ducklake.CATALOG}."{schema}"."{table}" at (version => {first})'
        right = f'{ducklake.CATALOG}."{schema}"."{table}" at (version => {second})'
        only_first = s3.scalar(
            conn, f"select count(*) from (select * from {left} except select * from {right})"
        )
        only_second = s3.scalar(
            conn, f"select count(*) from (select * from {right} except select * from {left})"
        )
        if only_first or only_second:
            differing.append(
                f"{schema}.{table}: {only_first} rows only in snapshot {first}, "
                f"{only_second} only in {second}. "
                f"{_column_report(conn, schema, table, first, second)}"
            )

    assert not differing, (
        f"{len(differing)} of {len(relations)} tables differ between two builds of one load:\n"
        + "\n".join(f"  {d}" for d in differing)
    )
