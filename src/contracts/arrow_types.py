"""Arrow type to DuckDB type, in one place.

`sources.yml` is generated from this map, so it is what dbt is told the snapshot's columns are.
Entries are added when a snapshot actually produces them, never speculatively.
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
    """Raise on an unmapped type rather than passing it through: dbt would get a type it does not
    know, and the error would surface far from its cause."""
    mapped = ARROW_TO_DUCKDB.get(arrow)
    if mapped is None:
        raise ToolingError(
            f"no DuckDB type mapped for Arrow type {arrow!r}. Add it to ARROW_TO_DUCKDB after "
            "checking what DuckDB actually reads the column as"
        )
    return mapped
