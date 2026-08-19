"""Every relation in the warehouse with its row and column count.

This exists so no document has to carry a row count. `docs/naming_convention.md` routes every
"how many rows" question here, which is why the command name outlives any module rename.
"""

from __future__ import annotations

import duckdb

from config import settings
from connectors import ducklake
from utils.exceptions import ToolingError


def report(conn: duckdb.DuckDBPyConnection) -> str:
    relations = ducklake.relations(conn)
    if not relations:
        raise ToolingError("the lake holds no relations -- run `make build` first")

    columns = dict(
        conn.execute(
            "select table_schema || '.' || table_name, count(*) "
            f"from information_schema.columns where table_catalog = '{ducklake.CATALOG}' group by 1"
        ).fetchall()
    )

    # Views have no stored count, so all must be counted -- one union query, not one per relation.
    counts = dict(
        conn.execute(
            " union all ".join(
                f"select '{schema}.{table}' as relation, count(*) as rows "
                f'from {ducklake.CATALOG}."{schema}"."{table}"'
                for schema, table, _ in relations
            )
        ).fetchall()
    )

    width = max(len(name) for name in columns)
    lines: list[str] = []
    layer = None
    for schema, table, kind in relations:
        name = f"{schema}.{table}"
        if schema != layer:
            lines.append(f"\n{schema}")
            layer = schema
        lines.append(
            f"  {name:<{width}}  {counts[name]:>9,} rows  {columns[name]:>3} columns  "
            f"{'table' if kind == 'BASE TABLE' else 'view'}"
        )

    lines.append(f"\n{len(relations)} relations, {sum(columns.values())} columns total")
    lines.append(f"lake at {settings.data_path()}, snapshot {ducklake.latest_snapshot(conn)}")
    return "\n".join(lines)
