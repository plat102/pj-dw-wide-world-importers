"""Extract the declared tables into the lake's raw schema: one dlt pipeline, one run.

dlt attaches the same DuckLake the warehouse is built in -- same catalog, same metadata schema,
same data path -- and loads each table into the `raw` schema. Nothing is staged locally, and
nothing describes what landed except the lake itself.
"""

from __future__ import annotations

from typing import Any

import dlt
import sqlalchemy as sa
from dlt.common.configuration.specs import AwsCredentials
from dlt.common.storages.configuration import FilesystemConfiguration
from dlt.destinations.impl.ducklake.configuration import DuckLakeCredentials
from dlt.sources.sql_database import sql_table

from config import settings
from connectors import ducklake, mssql
from ingestion import tables as tables_contract
from utils.exceptions import ToolingError

PIPELINE_NAME = "wwi_raw"


def destination() -> Any:
    """The lake the warehouse already lives in, as dlt's ducklake destination.

    Catalog, metadata schema and data path all have to match the ATTACH the dbt profile renders,
    or this writes a second lake into the same Postgres instead of the one dbt reads.
    """
    return dlt.destinations.ducklake(
        credentials=DuckLakeCredentials(
            ducklake_name=ducklake.CATALOG,
            metadata_schema=settings.METADATA_SCHEMA,
            # dlt parses a URL; duckdb's own ATTACH takes the libpq form. Same database.
            catalog=settings.catalog_url(),
            storage=FilesystemConfiguration(
                bucket_url=settings.data_path(),
                credentials=AwsCredentials(
                    aws_access_key_id=settings.require("S3_ACCESS_KEY"),
                    aws_secret_access_key=settings.require("S3_SECRET_KEY"),
                    endpoint_url=settings.endpoint_url(),
                    # Named because duckdb writes the secret verbatim: unset arrives as 'None'.
                    region_name="us-east-1",
                    s3_url_style="path",
                ),
            ),
        )
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


def extract(source_db: str) -> str:
    """Load the source into the lake's raw schema and report what landed."""
    specs = tables_contract.load()["tables"]

    engine = mssql.engine(mssql.connection_string(source_db))
    version = mssql.inspect_source(engine, source_db)
    mssql.check_declared_columns(engine, specs)
    expected = mssql.count_source_rows(engine, specs)

    # The pyarrow backend adds neither bookkeeping column by default. The row id stays off: it is
    # random per row, so two extractions of one source would never agree again.
    dlt.config["normalize.parquet_normalizer.add_dlt_load_id"] = True

    pipeline = dlt.pipeline(
        pipeline_name=PIPELINE_NAME,
        destination=destination(),
        dataset_name=settings.RAW_SCHEMA,
    )
    print(pipeline.run(resources(engine, specs), loader_file_format="parquet"))

    # Read back through an attach of our own, not dlt's: if the two ever stop naming one lake, it
    # surfaces here rather than three models into a build.
    conn = ducklake.connect()
    landed = ducklake.row_counts(conn, settings.RAW_SCHEMA, [e["output"] for e in specs])
    snapshot = ducklake.latest_snapshot(conn)
    conn.close()

    # Row-level security filters without raising, and usually only part of a table -- every
    # downstream check would then agree with itself on a short load.
    drift = {n: (expected[n], landed[n]) for n in landed if expected[n] != landed[n]}
    if drift:
        detail = ", ".join(
            f"{n}: source {a:,} vs landed {b:,}" for n, (a, b) in sorted(drift.items())
        )
        raise ToolingError(f"row counts do not match the source: {detail}")

    return (
        f"{ducklake.CATALOG}.{settings.RAW_SCHEMA}: {len(landed)} tables, "
        f"{sum(landed.values()):,} rows, lake snapshot {snapshot}\n"
        f"source {version}"
    )
