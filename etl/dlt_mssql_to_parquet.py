"""Extract the WWI source into a Parquet snapshot. Design: docs/ingestion/extraction_design.md

Reads a frozen database snapshot, not the live database. Connection from MSSQL_CONNECTION_STRING.

    python etl/dlt_mssql_to_parquet.py --snapshot-db WWI_Snap --output-dir data/raw
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import dlt
import yaml
from dlt.sources.sql_database import sql_table

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "etl" / "tables.yml"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot-db", default="WWI_Snap")
    p.add_argument("--output-dir", default="data/raw")
    p.add_argument("--tables-config", default=str(DEFAULT_CONFIG))
    p.add_argument("--load-timestamp", default=None, help="ISO 8601; defaults to now (UTC)")
    return p.parse_args()


def connection_string(snapshot_db: str) -> str:
    raw = os.environ.get("MSSQL_CONNECTION_STRING")
    if not raw:
        sys.exit("MSSQL_CONNECTION_STRING is not set")
    parts = urlsplit(raw)
    return urlunsplit((parts.scheme, parts.netloc, f"/{snapshot_db}", parts.query, parts.fragment))


def check_declared_columns(engine, tables: list[dict]) -> None:
    """Assert every declared column exists; dlt's included_columns silently drops unknown names."""
    import sqlalchemy as sa

    inspector = sa.inspect(engine)
    problems = []
    for entry in tables:
        schema, table = entry["source"].split(".")
        actual = {c["name"] for c in inspector.get_columns(table, schema=schema)}
        for missing in sorted(set(entry["columns"]) - actual):
            problems.append(f"{entry['source']}.{missing}")
    if problems:
        sys.exit("declared in etl/tables.yml but absent from the source: " + ", ".join(problems))


def count_source_rows(engine, tables: list[dict]) -> dict[str, int]:
    """Source row counts, to catch row-level security filtering part of a table."""
    import sqlalchemy as sa

    counts = {}
    with engine.connect() as conn:
        for entry in tables:
            schema, table = entry["source"].split(".")
            counts[entry["output"]] = conn.execute(
                sa.text(f"SELECT COUNT(*) FROM [{schema}].[{table}]")
            ).scalar()
    return counts


def inspect_source(conn_str: str, snapshot_db: str) -> dict[str, str]:
    """Verify the target is a snapshot and read the facts the manifest needs."""
    import sqlalchemy as sa

    engine = sa.create_engine(conn_str)
    with engine.connect() as conn:
        row = conn.execute(
            sa.text("SELECT source_database_id FROM sys.databases WHERE name = :db"),
            {"db": snapshot_db},
        ).fetchone()
        if row is None:
            sys.exit(f"{snapshot_db} does not exist -- run scripts/mssql/create_source_snapshot.sql")
        if row[0] is None:
            sys.exit(f"{snapshot_db} is a live database, not a snapshot; refusing to extract")

        version = conn.execute(
            sa.text(
                "SELECT CAST(SERVERPROPERTY('ProductVersion') AS varchar(30)) + ' ' "
                "+ CAST(SERVERPROPERTY('ProductLevel') AS varchar(20)) + ' ' "
                "+ CAST(SERVERPROPERTY('Edition') AS varchar(60))"
            )
        ).scalar()
        computed = conn.execute(
            sa.text(
                "SELECT COUNT(*) FROM sys.computed_columns "
                "WHERE object_id = OBJECT_ID('Sales.Invoices') AND name = 'ConfirmedDeliveryTime'"
            )
        ).scalar()
    return {
        "mssql_version": version,
        # ADR-0003: without the computed column, on-time needs ReturnedDeliveryData parsed downstream.
        "delivery_time_form": "computed_column" if computed else "raw_json",
    }


def clear_previous_run(out_dir: Path) -> None:
    """Delete only what a previous extraction wrote; rmtree would take the manifest too."""
    for path in out_dir.glob("*.parquet"):
        path.unlink()
    (out_dir / "_extraction.json").unlink(missing_ok=True)
    shutil.rmtree(out_dir / "_dlt", ignore_errors=True)


def main() -> int:
    args = parse_args()
    config = yaml.safe_load(Path(args.tables_config).read_text(encoding="utf-8"))
    tables = config["tables"]
    schema_version = config["schema_version"]

    conn_str = connection_string(args.snapshot_db)
    source_facts = inspect_source(conn_str, args.snapshot_db)

    import sqlalchemy as sa

    engine = sa.create_engine(conn_str)
    check_declared_columns(engine, tables)
    source_counts = count_source_rows(engine, tables)

    load_timestamp = args.load_timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    clear_previous_run(out_dir)

    staging = out_dir / "_dlt"
    pipeline = dlt.pipeline(
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
                credentials=conn_str,
                schema=schema,
                table=table,
                included_columns=entry["columns"],
                backend="pyarrow",
                reflection_level="full_with_precision",
                write_disposition="replace",
            ).with_name(entry["output"])
        )

    info = pipeline.run(resources, loader_file_format="parquet")
    print(info)

    written = flatten_output(staging, out_dir, tables)

    drift = {n: (source_counts[n], written[n]) for n in written if source_counts[n] != written[n]}
    if drift:
        detail = ", ".join(f"{n}: source {a:,} vs parquet {b:,}" for n, (a, b) in sorted(drift.items()))
        sys.exit(f"row counts do not match the source: {detail}")
    (out_dir / "_extraction.json").write_text(
        json.dumps(
            {
                "schema_version": schema_version,
                "load_timestamp": load_timestamp,
                "source_database": args.snapshot_db,
                **source_facts,
                "files": written,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n{len(written)} tables written to {out_dir}/ at load_timestamp {load_timestamp}")
    return 0


def flatten_output(staging: Path, out_dir: Path, tables: list[dict]) -> dict[str, int]:
    """dlt writes <dataset>/<table>/<load_id>.<id>.parquet; the contract wants one flat file."""
    import pyarrow.parquet as pq

    written: dict[str, int] = {}
    missing = [e["output"] for e in tables if not list(staging.rglob(f"{e['output']}/*.parquet"))]
    if missing:
        # Row-level security filters silently; a missing file is never success.
        sys.exit(f"no parquet produced for: {', '.join(missing)}")

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
            sys.exit(f"{name} extracted 0 rows; every declared table must carry data")
        written[name] = rows
    shutil.rmtree(staging, ignore_errors=True)
    return written


if __name__ == "__main__":
    raise SystemExit(main())
