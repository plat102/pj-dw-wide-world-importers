#!/usr/bin/env python
"""Expire old DuckLake snapshots and delete the data files they were holding.

A long-lived lake stops accepting writes if nothing expires. The current snapshot never expires,
so only time travel is lost.

    python -m scripts.lake_retention --dry-run     # or: make compact_dry
    python -m scripts.lake_retention               # or: make compact
"""

from __future__ import annotations

import argparse
import os

from scripts.warehouse import connect, data_path, s3fs_client


def measure(fs, prefix: str) -> tuple[int, int]:
    """Object count and total bytes under a prefix, from one listing."""
    listing = fs.find(prefix, detail=True)
    return len(listing), sum(info["size"] for info in listing.values())


def report(label: str, objects: int, size: int) -> None:
    print(f"  {label:<8} {objects:>5} objects  {size / 1024 / 1024:>8.2f} MiB")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--older-than-days",
        type=float,
        default=float(os.environ.get("LAKE_RETENTION_DAYS", 7)),
        help="expire snapshots older than this many days (default 7, or LAKE_RETENTION_DAYS)",
    )
    parser.add_argument("--dry-run", action="store_true", help="report what would happen only")
    args = parser.parse_args()

    conn = connect()
    fs = s3fs_client()
    prefix = data_path().removeprefix("s3://").rstrip("/")
    cutoff = f"now() - to_seconds({int(args.older_than_days * 86400)})"

    total = conn.execute("select count(*) from ducklake_snapshots('lake')").fetchone()[0]
    # DuckLake's own dry run is the authority on what the window covers, and it already excludes
    # the current snapshot. Asking it beats reimplementing the rule here.
    expiring = conn.execute(
        f"select count(*) from ducklake_expire_snapshots('lake', older_than => {cutoff}, "
        "dry_run => true)"
    ).fetchone()[0]

    print(f"lake at {data_path()}")
    print(f"  {total} snapshots, {expiring} older than {args.older_than_days:g} day(s)")

    objects_before, size_before = measure(fs, prefix)
    print("\nbefore:")
    report("store", objects_before, size_before)

    if not expiring:
        print("\nnothing to expire; the store is already at its retained size")
        return 0

    if args.dry_run:
        print(f"\ndry run: would expire {expiring} snapshot(s) and the files only they referenced")
        return 0

    # Order matters: a file only becomes eligible for cleanup once the snapshot that referenced it
    # is gone, so expiring second would reclaim nothing.
    conn.execute(f"call ducklake_expire_snapshots('lake', older_than => {cutoff})")
    conn.execute("call ducklake_cleanup_old_files('lake', cleanup_all => true)")
    # Files the catalog never knew about -- an interrupted write leaves these behind.
    conn.execute("call ducklake_delete_orphaned_files('lake', cleanup_all => true)")

    objects_after, size_after = measure(fs, prefix)
    print("\nafter:")
    report("store", objects_after, size_after)
    remaining = conn.execute("select count(*) from ducklake_snapshots('lake')").fetchone()[0]
    print(
        f"\nexpired {expiring} snapshot(s), removed {objects_before - objects_after} object(s), "
        f"reclaimed {(size_before - size_after) / 1024 / 1024:.2f} MiB; "
        f"{remaining} snapshot(s) remain"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
