"""Extract the declared tables to local Parquet, one dlt resource per call.

Staged locally first so the manifest's SHA256 covers exactly the bytes the upload publishes. The
resources are extracted one at a time because dlt interleaves them within a single call and one
connection holds one result set -- interleaving is what would break the one-transaction guarantee.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import dlt
import pyarrow.parquet as pq
from dlt.sources.sql_database import sql_table

from connectors import mssql
from contracts import tables as tables_contract
from utils.exceptions import ToolingError


def clear_previous_run(out_dir: Path) -> None:
    """Delete only what a previous extraction wrote; rmtree would take the manifest too."""
    for path in out_dir.glob("*.parquet"):
        path.unlink()
    (out_dir / "_extraction.json").unlink(missing_ok=True)
    shutil.rmtree(out_dir / "_dlt", ignore_errors=True)


def extract(source_db: str, output_dir: Path) -> str:
    """Read every declared table inside one transaction and write Parquet. Returns a summary."""
    config = tables_contract.load()
    tables = config["tables"]
    schema_version = config["schema_version"]

    conn_str = mssql.connection_string(source_db)
    source_facts = mssql.inspect_source(conn_str, source_db)

    engine = mssql.pinned_engine(conn_str)
    raw, cursor, transaction_id = mssql.open_snapshot_transaction(engine)
    mssql.check_declared_columns(engine, tables)
    source_counts = mssql.count_source_rows(engine, tables)

    load_timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    out_dir = output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    clear_previous_run(out_dir)

    # Staged locally so the manifest's SHA256 covers exactly the bytes the upload publishes.
    staging = out_dir / "_dlt"
    # Ignored below: dlt's pipeline() overloads accept only the string form of `destination`,
    # but the Destination instance is what carries bucket_url, so the instance is what we pass.
    pipeline = dlt.pipeline(  # type: ignore[call-overload]
        pipeline_name="wwi_snapshot",
        destination=dlt.destinations.filesystem(bucket_url=staging.as_uri()),
        dataset_name="raw",
        progress=None,
    )

    resources = []
    for entry in tables:
        schema, table = entry["source"].split(".")
        resources.append(
            sql_table(
                credentials=engine,
                schema=schema,
                table=table,
                included_columns=entry["columns"],
                backend="pyarrow",
                reflection_level="full_with_precision",
                write_disposition="replace",
            ).with_name(entry["output"])
        )

    # Split rather than `pipeline.run` so the transaction ends with the reads. One resource per
    # call, because dlt interleaves them within a call and one connection holds one result set.
    for resource in resources:
        pipeline.extract([resource], loader_file_format="parquet", workers=1)

    # Before anything is published: the files would be each valid and collectively wrong.
    mssql.assert_same_transaction(cursor, transaction_id)
    cursor.execute("COMMIT TRANSACTION")
    raw.close()

    pipeline.normalize()
    print(pipeline.load())

    written = flatten_output(staging, out_dir, tables)

    drift = {n: (source_counts[n], written[n]) for n in written if source_counts[n] != written[n]}
    if drift:
        detail = ", ".join(
            f"{n}: source {a:,} vs parquet {b:,}" for n, (a, b) in sorted(drift.items())
        )
        raise ToolingError(f"row counts do not match the source: {detail}")
    (out_dir / "_extraction.json").write_text(
        json.dumps(
            {
                "schema_version": schema_version,
                "load_timestamp": load_timestamp,
                "source_database": source_db,
                **source_facts,
                "files": written,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return f"{len(written)} tables written to {out_dir}/ at load_timestamp {load_timestamp}"


def flatten_output(staging: Path, out_dir: Path, tables: list[dict]) -> dict[str, int]:
    """dlt writes <dataset>/<table>/<load_id>.<id>.parquet; the contract wants one flat file."""
    written: dict[str, int] = {}
    missing = [e["output"] for e in tables if not list(staging.rglob(f"{e['output']}/*.parquet"))]
    if missing:
        # Row-level security filters silently; a missing file is never success.
        raise ToolingError(f"no parquet produced for: {', '.join(missing)}")

    for entry in tables:
        name = entry["output"]
        parts = sorted(staging.rglob(f"{name}/*.parquet"))
        target = out_dir / f"{name}.parquet"
        if len(parts) == 1:
            shutil.move(str(parts[0]), target)
        else:
            table = pq.read_table([str(p) for p in parts])
            pq.write_table(table, target, compression="snappy")
        rows = pq.ParquetFile(target).metadata.num_rows
        if rows == 0:
            raise ToolingError(f"{name} extracted 0 rows; every declared table must carry data")
        written[name] = rows
    shutil.rmtree(staging, ignore_errors=True)
    return written

