"""Keep the lake from growing without bound: expire old snapshots, merge small files, delete what
no kept snapshot reads.

Every extract, build and compare writes a full copy, and time travel keeps each one -- sensitive
columns included -- until a snapshot is expired. A store that fills up fails the next load halfway.

The newest snapshot is never expired, whatever the retention. `make compare` builds its own two
snapshots, so it needs none of the old ones.
"""

from __future__ import annotations

import duckdb

from connectors import ducklake
from utils.exceptions import ToolingError


def _run(conn: duckdb.DuckDBPyConnection, call: str) -> list[tuple]:
    try:
        return conn.execute(call).fetchall()
    except duckdb.Error as error:
        raise ToolingError(f"maintenance stopped at `{call}`: {error}") from error


def run(
    conn: duckdb.DuckDBPyConnection,
    keep_days: int,
    dry_run: bool = False,
    catalog: str = ducklake.CATALOG,
) -> str:
    """Each step in the order DuckLake's CHECKPOINT runs them, stated rather than bundled, so the
    retention is this function's argument and not a catalog option set somewhere else.
    """
    if keep_days < 0:
        raise ToolingError(f"--keep-days must be 0 or more, got {keep_days}")
    cutoff = f"now() - interval '{int(keep_days)} days'"
    dry = ", dry_run => true" if dry_run else ""

    expired = _run(
        conn, f"call ducklake_expire_snapshots('{catalog}', older_than => {cutoff}{dry})"
    )
    # No dry run for merging. It is safe for time travel anyway: a kept snapshot reads the merged
    # file, and only the files it replaced are scheduled for deletion. It commits a snapshot of
    # its own when it merges anything.
    merged = [] if dry_run else _run(conn, f"call ducklake_merge_adjacent_files('{catalog}')")
    # Everything scheduled is safe to delete now: a file is scheduled only once no kept snapshot
    # reads it.
    deleted = _run(conn, f"call ducklake_cleanup_old_files('{catalog}', cleanup_all => true{dry})")
    # Files no snapshot ever recorded, left by a write that failed before its commit. The cutoff
    # keeps the files of a write still in flight out of reach.
    orphans = _run(
        conn, f"call ducklake_delete_orphaned_files('{catalog}', older_than => {cutoff}{dry})"
    )

    left = conn.execute(f"select count(*) from ducklake_snapshots('{catalog}')").fetchone()
    rows = [
        ("snapshots expired", str(len(expired))),
        (
            "files merged",
            "skipped, it has no dry run"
            if dry_run
            else f"{sum(row[2] for row in merged)} into {sum(row[3] for row in merged)}",
        ),
        ("old files deleted", str(len(deleted))),
        ("orphaned files deleted", str(len(orphans))),
        ("snapshots left", str(left[0] if left else 0)),
    ]
    header = f"kept {keep_days} days of snapshots on {catalog}"
    if dry_run:
        # Expiring is what schedules most files, so a dry run undercounts them.
        header += " -- dry run, nothing changed; old files counts only those already scheduled"
    return "\n".join([header, *(f"  {label:<24}{value}" for label, value in rows)])
