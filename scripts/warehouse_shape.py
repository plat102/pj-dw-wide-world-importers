#!/usr/bin/env python
"""Print every relation in the warehouse with its row and column count.

Exists so no document has to carry a row count; read through a fresh connection.

    python -m scripts.warehouse_shape       # or: make shape
"""

from __future__ import annotations

import sys

from scripts.warehouse import connect, data_path


def main() -> int:
    conn = connect()
    relations = conn.execute(
        """
        select table_schema, table_name, table_type
        from information_schema.tables
        where table_catalog = 'lake'
        order by table_schema, table_name
        """
    ).fetchall()
    if not relations:
        sys.exit("the lake holds no relations -- run `make build` first")

    columns = dict(
        conn.execute(
            "select table_schema || '.' || table_name, count(*) "
            "from information_schema.columns where table_catalog = 'lake' group by 1"
        ).fetchall()
    )

    # Views have no stored count, so all must be counted -- one union query, not 26 round trips.
    counts = dict(
        conn.execute(
            " union all ".join(
                f"select '{schema}.{table}' as relation, count(*) as rows "
                f'from lake."{schema}"."{table}"'
                for schema, table, _ in relations
            )
        ).fetchall()
    )

    width = max(len(name) for name in columns)
    layer = None
    for schema, table, kind in relations:
        name = f"{schema}.{table}"
        if schema != layer:
            print(f"\n{schema}")
            layer = schema
        print(
            f"  {name:<{width}}  {counts[name]:>9,} rows  {columns[name]:>3} columns  "
            f"{'table' if kind == 'BASE TABLE' else 'view'}"
        )

    snapshot = conn.execute("select max(snapshot_id) from ducklake_snapshots('lake')").fetchone()[0]
    print(f"\n{len(relations)} relations, {sum(columns.values())} columns total")
    print(f"lake at {data_path()}, snapshot {snapshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
