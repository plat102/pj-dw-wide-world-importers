"""Cut a small, real, committable slice of the snapshot so a fresh clone has something to query.

The shipped snapshot is 24 MB and git-ignored on principle. This is a different artifact: a reduced
derivative, committed, labelled `kind: demo_fixture`, with its own manifest and its own real
checksums. It exists so `make demo` can run the real seed-and-verify path instead of the
schema-only one, and so the warehouse a reader builds returns numbers rather than empty relations.

Written with pyarrow rather than DuckDB `COPY` so every column keeps the exact Arrow type the
extraction produced: verify_snapshot.py compares column types, and sources.yml is generated from
those types.

    wwi demo-fixture       # or: make demo_fixture
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from contracts import manifest as manifest_contract
from contracts.paths import snapshot_id
from utils.exceptions import ToolingError

# Only the four fact-shaped tables are reduced. The other 17 total under a megabyte and are kept
# whole on purpose: a fixture whose foreign keys resolve because the dimension was filtered to
# match is not testing referential integrity, it is hiding the absence of it.
ORDERS = "sales__orders"
ORDER_LINES = "sales__order_lines"
INVOICES = "sales__invoices"
TRANSACTIONS = "warehouse__stock_item_transactions"

# How many missing tables the error names before trailing off; the rest are counted, not listed.
NAMED_IN_ERROR = 3


def sorted_by_first_column(table: pa.Table) -> pa.Table:
    """Impose a row order so regenerating the fixture reproduces it byte for byte.

    The extraction cannot promise this -- SQL Server guarantees no order without ORDER BY, and five
    of the 21 tables came back reordered when that was re-measured. The fixture can, because it
    imposes one.
    """
    return table.sort_by([(table.schema.names[0], "ascending")])


def cut(in_dir: Path, out_dir: Path, src_manifest_path: Path, from_date: str) -> str:
    source = manifest_contract.load(src_manifest_path)

    missing = [n for n in source["tables"] if not (in_dir / f"{n}.parquet").exists()]
    if missing:
        raise ToolingError(
            f"{in_dir} is missing {len(missing)} of the snapshot's tables "
            f"({', '.join(missing[:NAMED_IN_ERROR])}"
            f"{'...' if len(missing) > NAMED_IN_ERROR else ''}) -- "
            "run `make extract` on a machine with the source"
        )

    cutoff = pa.scalar(datetime.fromisoformat(from_date).date(), type=pa.date32())

    # Orders first: everything else keys off which orders survive.
    orders = pq.read_table(in_dir / f"{ORDERS}.parquet")
    orders = orders.filter(pc.greater_equal(orders["order_date"], cutoff))
    kept_order_ids = orders["order_id"].combine_chunks()

    invoices = pq.read_table(in_dir / f"{INVOICES}.parquet")
    invoices = invoices.filter(pc.is_in(invoices["order_id"], value_set=kept_order_ids))
    kept_invoice_ids = invoices["invoice_id"].combine_chunks()

    order_lines = pq.read_table(in_dir / f"{ORDER_LINES}.parquet")
    order_lines = order_lines.filter(pc.is_in(order_lines["order_id"], value_set=kept_order_ids))

    # Two conditions, and both are load-bearing. The date keeps the movement history coherent with
    # the orders; the invoice test keeps it referentially closed. Filtering on the date alone leaves
    # 153 stock issues whose invoice belongs to an order from before the window, and a fact built on
    # those would fail a relationship test for a reason that has nothing to do with the model.
    txns = pq.read_table(in_dir / f"{TRANSACTIONS}.parquet")
    in_window = pc.greater_equal(
        pc.cast(txns["transaction_occurred_when"], pa.date32()), cutoff
    )
    resolves = pc.or_(
        pc.is_null(txns["invoice_id"]),
        pc.is_in(txns["invoice_id"], value_set=kept_invoice_ids),
    )
    txns = txns.filter(pc.and_(in_window, resolves))

    reduced = {
        ORDERS: orders,
        ORDER_LINES: order_lines,
        INVOICES: invoices,
        TRANSACTIONS: txns,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.parquet"):
        stale.unlink()

    tables: dict[str, dict[str, Any]] = {}
    for name in source["tables"]:
        table = reduced.get(name) or pq.read_table(in_dir / f"{name}.parquet")
        table = sorted_by_first_column(table)
        dest = out_dir / f"{name}.parquet"
        pq.write_table(table, dest, compression="snappy")

        tables[name] = manifest_contract.describe_file(dest)

        expected = source["tables"][name]["columns"]
        if tables[name]["columns"] != expected:
            drifted = [c for c in expected if expected.get(c) != tables[name]["columns"].get(c)]
            raise ToolingError(
                f"{name}: the fixture's column types differ from the snapshot's "
                f"({', '.join(drifted)})"
                " -- sources.yml is generated from the snapshot's types, so the two must agree"
            )

    # The `demo-` prefix gives the fixture its own bronze prefix, so seeding it can never
    # overwrite a published snapshot. The timestamp is the source's rather than the wall clock's,
    # so the fixture derived from one snapshot always carries one id.
    manifest = {
        "schema_version": source["schema_version"],
        "snapshot_timestamp": source["snapshot_timestamp"],
        "snapshot_id": f"demo-{snapshot_id(source['snapshot_timestamp'])}",
        "kind": "demo_fixture",
        "derived_from": source["snapshot_id"],
        "orders_from_date": from_date,
        "mssql_version": source["mssql_version"],
        "delivery_time_form": source["delivery_time_form"],
        **manifest_contract.summarise(tables),
        "tables": tables,
    }

    out = out_dir / "manifest.json"
    manifest_contract.dump(manifest, out)

    mb = manifest["total_size_bytes"] / 1048576
    lines = [f"{out}: {len(tables)} tables, {manifest['total_row_count']:,} rows, {mb:.2f} MB"]
    # Built before the f-string rather than inside it: nesting the same quote three deep parses
    # only on 3.12+, and this file is not the place to raise the floor for the whole project.
    reduced_counts = ", ".join(f"{name} {tables[name]['row_count']:,}" for name in reduced)
    lines.append(f"  reduced: {reduced_counts}")
    lines.append(
        f"  snapshot_id: {manifest['snapshot_id']} (derived from {manifest['derived_from']})"
    )
    return "\n".join(lines)
