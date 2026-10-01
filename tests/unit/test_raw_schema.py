"""src/ingestion/raw_schema.sql must describe the raw schema the extraction produces.

It is generated from a loaded lake, so nothing regenerates it when tables.yml changes. These tests
build it into a local lake -- the same step `make build_empty` runs -- and hold it to the contract,
naming every column the way dlt names it.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
from dlt.common.normalizers.naming.snake_case import NamingConvention

from config import settings
from ingestion import raw_schema
from ingestion import tables as tables_contract
from utils.exceptions import ToolingError
from utils.sql import literal

# Every row dlt writes carries this; it is what staging turns into `processed_at`.
LOAD_ID = "_dlt_load_id"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, list[str]]:
    """raw_schema.sql built into a fresh local lake: table -> columns, as DuckLake reports them."""
    directory = tmp_path_factory.mktemp("empty_lake")
    raw_schema.create(directory)
    conn = duckdb.connect()
    conn.execute("load ducklake")
    conn.execute(f"attach {literal('ducklake:' + str(directory / 'metadata.ducklake'))} as lake")
    rows = conn.execute(
        "select table_name, column_name from information_schema.columns "
        "where table_catalog = 'lake' and table_schema = ? order by table_name, ordinal_position",
        [settings.RAW_SCHEMA],
    ).fetchall()
    conn.close()
    columns: dict[str, list[str]] = {}
    for table, column in rows:
        columns.setdefault(table, []).append(column)
    return columns


def test_it_holds_exactly_the_tables_dbt_reads(built: dict[str, list[str]]) -> None:
    assert sorted(built) == raw_schema.expected_tables()


def test_every_contract_table_has_exactly_its_declared_columns(
    built: dict[str, list[str]],
) -> None:
    """A column added to tables.yml but not to raw_schema.sql would build in CI as absent."""
    naming = NamingConvention()
    wrong = {}
    for entry in tables_contract.load()["tables"]:
        declared = {naming.normalize_identifier(column) for column in entry["columns"]} | {LOAD_ID}
        present = set(built[entry["output"]])
        if declared != present:
            wrong[entry["output"]] = {
                "only in tables.yml": sorted(declared - present),
                "only in raw_schema.sql": sorted(present - declared),
            }
    assert not wrong, f"raw_schema.sql is stale -- run `make raw_schema`: {wrong}"


def test_it_is_rebuilt_from_scratch(tmp_path: Path) -> None:
    """A lake left by the previous run holds the models it built; the build must start from raw."""
    stale = tmp_path / "data" / "leftover.parquet"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"")
    raw_schema.create(tmp_path)
    assert not stale.exists()


def test_a_missing_schema_file_says_how_to_make_one(tmp_path: Path) -> None:
    with pytest.raises(ToolingError, match="make raw_schema"):
        raw_schema.create(tmp_path / "lake", schema_ddl=tmp_path / "absent.sql")
