"""dbt's sources must name exactly what the extraction produces.

`sources.yml` is hand-written now, so nothing regenerates it into agreement. This is the gate
that used to be `make sources --check`: same guarantee, taken from the two files that define the
contract, and it needs no warehouse.
"""

from __future__ import annotations

from typing import Any

import yaml

from config import settings
from ingestion import tables as tables_contract

SOURCES = settings.DBT_DIR / "models" / "sources.yml"


def _source() -> dict[str, Any]:
    parsed = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    sources = parsed["sources"]
    assert len(sources) == 1, "one source, or these assertions are naming the wrong one"
    return sources[0]


def test_sources_name_exactly_the_extracted_tables() -> None:
    declared = {entry["output"] for entry in tables_contract.load()["tables"]}
    published = {table["name"] for table in _source()["tables"]}
    assert published == declared, (
        f"sources.yml and tables.yml disagree: only in sources {sorted(published - declared)}, "
        f"only in tables {sorted(declared - published)}"
    )


def test_sources_address_the_lake_the_extraction_writes() -> None:
    """The source resolves by name, so these two strings are the whole address."""
    source = _source()
    assert source["schema"] == settings.BRONZE_SCHEMA
    assert source["database"] == "lake"


def test_no_source_reads_parquet_directly() -> None:
    """`external_location` wins over database.schema, so leaving one behind silently bypasses
    the catalog and the source points at files again."""
    assert "external_location" not in SOURCES.read_text(encoding="utf-8")
