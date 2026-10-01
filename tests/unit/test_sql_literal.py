"""utils.sql.literal: a value with a quote in it must survive DuckDB's parser unchanged."""

from __future__ import annotations

import duckdb
import pytest

from utils.sql import literal


@pytest.mark.parametrize("value", ["plain", "it's", "''", "a'b'c", "back\\slash", ""])
def test_duckdb_reads_back_exactly_the_value(value: str) -> None:
    assert duckdb.connect().execute(f"select {literal(value)}").fetchone() == (value,)
