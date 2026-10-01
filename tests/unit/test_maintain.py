"""warehouse.maintain on a real DuckLake: a DuckDB-file catalog and a local data path, so the same
maintenance calls run as on the stack, with no store and no Postgres.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from utils.exceptions import ToolingError
from utils.sql import literal
from warehouse import maintain

CATALOG = "lake"


@pytest.fixture
def lake(tmp_path: Path) -> Iterator[tuple[duckdb.DuckDBPyConnection, Path]]:
    """Four "builds" of one table, each a replace and an append: eight files, nine snapshots."""
    data = tmp_path / "data"
    data.mkdir()
    conn = duckdb.connect()
    conn.execute("install ducklake")
    conn.execute("load ducklake")
    # Inlining off: small inserts would otherwise land in the catalog, and no file would be written.
    conn.execute(
        f"attach {literal('ducklake:' + str(tmp_path / 'meta.ducklake'))} as {CATALOG} "
        f"(data_path {literal(str(data) + '/')}, data_inlining_row_limit 0)"
    )
    conn.execute(f"use {CATALOG}")
    for build in range(4):
        conn.execute(
            f"create or replace table t as select range as id, {build} as b from range(100)"
        )
        conn.execute(f"insert into t select range + 1000, {build} from range(100)")
    yield conn, data
    conn.close()


def _snapshots(conn: duckdb.DuckDBPyConnection) -> list[int]:
    rows = conn.execute(f"select snapshot_id from ducklake_snapshots('{CATALOG}') order by 1")
    return [row[0] for row in rows.fetchall()]


def _files(data: Path) -> set[Path]:
    return {path for path in data.rglob("*") if path.is_file()}


def _contents(conn: duckdb.DuckDBPyConnection, version: int | None = None) -> tuple:
    at = f" at (version => {version})" if version is not None else ""
    row = conn.execute(f"select count(*), sum(id), sum(b) from t{at}").fetchone()
    assert row is not None
    return tuple(row)


def test_zero_days_keeps_only_the_newest_snapshot_and_its_data(
    lake: tuple[duckdb.DuckDBPyConnection, Path],
) -> None:
    conn, data = lake
    before_files = _files(data)
    newest = _snapshots(conn)[-1]
    current = _contents(conn)

    maintain.run(conn, keep_days=0, catalog=CATALOG)

    # Merging commits a snapshot of its own, after the expiry; nothing older than `newest` is left.
    assert [version for version in _snapshots(conn) if version <= newest] == [newest]
    assert _contents(conn) == current
    assert len(_files(data)) < len(before_files), "expired snapshots' files were not deleted"


def test_a_kept_snapshot_still_reads_the_same_after_merge_and_cleanup(
    lake: tuple[duckdb.DuckDBPyConnection, Path],
) -> None:
    """Merging rewrites files a kept snapshot reads; time travel must not notice."""
    conn, _ = lake
    snapshots = _snapshots(conn)
    before = {version: _contents(conn, version) for version in snapshots[-4:]}

    report = maintain.run(conn, keep_days=7, catalog=CATALOG)

    assert set(snapshots) <= set(_snapshots(conn)), "a snapshot inside the retention was expired"
    assert {version: _contents(conn, version) for version in before} == before
    assert "snapshots expired       0" in report


def test_a_dry_run_changes_nothing(lake: tuple[duckdb.DuckDBPyConnection, Path]) -> None:
    conn, data = lake
    snapshots, files = _snapshots(conn), _files(data)

    report = maintain.run(conn, keep_days=0, dry_run=True, catalog=CATALOG)

    assert _snapshots(conn) == snapshots
    assert _files(data) == files
    # It still says what would go.
    assert f"snapshots expired       {len(snapshots) - 1}" in report


def test_an_old_orphan_is_deleted_and_a_recent_one_kept(
    lake: tuple[duckdb.DuckDBPyConnection, Path],
) -> None:
    """An orphan is a file no snapshot recorded -- what a load that failed before commit leaves."""
    conn, data = lake
    old, recent = data / "main" / "t" / "old-orphan.parquet", data / "main" / "t" / "new.parquet"
    for path in (old, recent):
        conn.execute(f"copy (select 1 as x) to {literal(str(path))} (format parquet)")
    month_ago = time.time() - 30 * 86400
    os.utime(old, (month_ago, month_ago))

    maintain.run(conn, keep_days=7, catalog=CATALOG)

    assert not old.exists()
    assert recent.exists(), "a file younger than the retention may belong to a write in flight"


def test_a_negative_retention_is_refused(lake: tuple[duckdb.DuckDBPyConnection, Path]) -> None:
    conn, _ = lake
    with pytest.raises(ToolingError, match="--keep-days"):
        maintain.run(conn, keep_days=-1, catalog=CATALOG)
