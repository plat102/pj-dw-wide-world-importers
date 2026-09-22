"""Extract the declared tables into the bronze layer: one dlt pipeline, one run.

dlt's filesystem destination writes each table straight to
`s3://<bucket>/bronze/<snapshot-id>/<table>/`, and the manifest is then written from what actually
landed there, read back through the S3 API. Nothing is staged locally.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import dlt
import sqlalchemy as sa
from dlt.sources.sql_database import sql_table

from config import settings
from connectors import mssql, s3
from contracts import manifest as manifest_contract
from contracts import tables as tables_contract
from contracts.paths import bronze_prefix, snapshot_id
from utils.exceptions import ToolingError

PIPELINE_NAME = "wwi_snapshot"
# What `replace` requires: {table_name} first, with a separator after it.
LAYOUT = "{table_name}/{load_id}.{file_id}.{ext}"
# bronze/ is the bucket_url; the snapshot id is the dataset. dlt normalises dataset_name unless
# that is switched off, which would lowercase the id and stop the prefix matching the manifest.
BRONZE_ROOT = "bronze"


def destination() -> Any:
    return dlt.destinations.filesystem(
        bucket_url=f"s3://{settings.bucket()}/{BRONZE_ROOT}",
        layout=LAYOUT,
        enable_dataset_name_normalization=False,
        credentials={
            "aws_access_key_id": settings.require("S3_ACCESS_KEY"),
            "aws_secret_access_key": settings.require("S3_SECRET_KEY"),
            "endpoint_url": settings.endpoint_url(),
        },
    )


def resources(engine: sa.Engine, specs: list[dict]) -> list[Any]:
    """One standalone `sql_table` resource per declared table.

    Columns are named rather than reflected wholesale, and `full_with_precision` keeps decimal
    scale and datetime precision intact.
    """
    built = []
    for entry in specs:
        schema, table = entry["source"].split(".")
        built.append(
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
    return built


def extract(source_db: str, output: Path) -> str:
    """Load the source into bronze and write the manifest describing what landed."""
    config = tables_contract.load()
    specs = config["tables"]

    engine = mssql.engine(mssql.connection_string(source_db))
    facts = mssql.inspect_source(engine, source_db)
    mssql.check_declared_columns(engine, specs)
    expected_rows = mssql.count_source_rows(engine, specs)

    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    identifier = snapshot_id(timestamp)

    pipeline = dlt.pipeline(
        pipeline_name=PIPELINE_NAME,
        destination=destination(),
        dataset_name=identifier,
    )
    print(pipeline.run(resources(engine, specs), loader_file_format="parquet"))

    prefix = bronze_prefix(identifier)
    tables = manifest_contract.from_store(
        s3.client(), settings.bucket(), prefix, [e["output"] for e in specs]
    )
    # Row-level security filters without raising, and usually only part of a table -- every
    # downstream check would then agree with itself on a short snapshot.
    drift = {
        n: (expected_rows[n], t["row_count"])
        for n, t in tables.items()
        if expected_rows[n] != t["row_count"]
    }
    if drift:
        detail = ", ".join(
            f"{n}: source {a:,} vs landed {b:,}" for n, (a, b) in sorted(drift.items())
        )
        raise ToolingError(f"row counts do not match the source: {detail}")

    manifest = {
        "schema_version": config["schema_version"],
        "snapshot_timestamp": timestamp,
        "snapshot_id": identifier,
        **facts,
        **manifest_contract.summarise(tables),
        "tables": tables,
    }
    manifest_contract.dump(manifest, output)

    mb = manifest["total_size_bytes"] / 1048576
    return (
        f"s3://{settings.bucket()}/{prefix}/: {len(tables)} tables, "
        f"{manifest['total_row_count']:,} rows, {mb:.1f} MB\n"
        f"{output}: written"
    )
