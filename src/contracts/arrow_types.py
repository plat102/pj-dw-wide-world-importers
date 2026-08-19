"""Arrow type to DuckDB type, in one place.

`sources.yml` is generated from these and the zero-row seed writes Parquet with them, so the two
must agree by construction. They previously disagreed about failure: the generator exited on an
unmapped type while the seeder caught KeyError and carried on.

Arrow types are what the extraction sees; dbt wants the warehouse's names. Checked column by column
against `describe select * from read_parquet(...)`: no Arrow type maps to two DuckDB types. Entries
are added when a snapshot actually produces them, never speculatively -- an unverified row here is
a wrong type in every model that reads the column.
"""

from __future__ import annotations

from utils.exceptions import ToolingError

ARROW_TO_DUCKDB = {
    "bool": "BOOLEAN",
    "date32[day]": "DATE",
    "decimal128(18, 2)": "DECIMAL(18,2)",
    "decimal128(18, 3)": "DECIMAL(18,3)",
    "int64": "BIGINT",
    "string": "VARCHAR",
    "timestamp[us]": "TIMESTAMP",
}


def duckdb_type(arrow: str) -> str:
    """Fail loudly on an unmapped type rather than guessing or passing it through.

    A new Arrow type means the snapshot gained a column shape nobody has checked against DuckDB.
    Silently emitting the Arrow name would give dbt a type it does not know, and the error would
    surface far from its cause.
    """
    mapped = ARROW_TO_DUCKDB.get(arrow)
    if mapped is None:
        raise ToolingError(
            f"no DuckDB type mapped for Arrow type {arrow!r}. Add it to ARROW_TO_DUCKDB after "
            "checking what DuckDB actually reads the column as"
        )
    return mapped
