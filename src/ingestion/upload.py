"""Publish a Parquet snapshot to the object store's bronze layer.

Refuses any file whose SHA256 disagrees with the manifest: uploading it would put bytes on the
store that the manifest disowns, and the manifest is the only thing a consumer can check against.

`seed_empty` writes zero-row Parquet carrying the manifest's columns and types instead. That checks
the schema, not the checksum -- an empty file is a different artifact by design -- and it exists for
a pure schema-break check. It is not what CI builds on: on no rows every data-dependent test passes
trivially.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from connectors import s3
from contracts.arrow_types import duckdb_type
from utils.checksums import sha256_file
from utils.exceptions import ToolingError


def published_snapshot_present(fs: Any, bucket: str, prefix: str, manifest: dict) -> bool:
    """True when the real snapshot already occupies these keys: one listing against its sizes."""
    sizes = {
        key.rsplit("/", 1)[-1]: info["size"]
        for key, info in fs.find(f"{bucket}/{prefix}/", detail=True).items()
    }
    return all(
        sizes.get(entry["file"]) == entry["size_bytes"] for entry in manifest["tables"].values()
    )


def seed_empty(manifest: dict, bucket: str, prefix: str) -> list[str]:
    conn = s3.connection()
    problems: list[str] = []

    for table, entry in sorted(manifest["tables"].items()):
        target = f"s3://{bucket}/{prefix}/{entry['file']}"
        columns = entry["columns"]
        try:
            expected = {name: duckdb_type(arrow) for name, arrow in columns.items()}
        except ToolingError as error:
            problems.append(f"{table}: {error}")
            continue
        selected = ", ".join(f'cast(null as {kind}) as "{name}"' for name, kind in expected.items())
        # `where false` gives the right schema and no rows.
        conn.execute(f"copy (select {selected} where false) to '{target}' (format parquet)")

        described = conn.execute(f"describe select * from read_parquet('{target}')").fetchall()
        actual = {name: kind for name, kind, *_ in described}
        if actual != expected:
            retyped = [
                f"{c}: {expected[c]} -> {actual[c]}"
                for c in expected
                if c in actual and actual[c] != expected[c]
            ]
            problems.append(
                f"{table}: written schema disagrees with the manifest -- "
                f"missing {[c for c in expected if c not in actual]}, "
                f"extra {[c for c in actual if c not in expected]}, retyped {retyped}"
            )
        rows = s3.scalar(conn, f"select count(*) from read_parquet('{target}')")
        if rows:
            problems.append(f"{table}: expected zero rows, got {rows}")
    return problems


def upload(manifest: dict, fs: Any, bucket: str, prefix: str, data_dir: Path) -> list[str]:
    problems: list[str] = []
    for table, entry in sorted(manifest["tables"].items()):
        local = data_dir / entry["file"]
        if not local.exists():
            problems.append(f"{table}: {local} is missing locally")
            continue
        actual = sha256_file(local)
        if actual != entry["sha256"]:
            problems.append(
                f"{table}: local checksum {actual[:12]} does not match manifest "
                f"{entry['sha256'][:12]} -- refusing to upload"
            )
            continue
        fs.put_file(str(local), f"{bucket}/{prefix}/{entry['file']}")
    return problems
