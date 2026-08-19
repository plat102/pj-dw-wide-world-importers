"""Cut a small, real, committable slice of the snapshot so a fresh clone has something to query.

The shipped snapshot is 24 MB and git-ignored on principle. This is a different artifact: a reduced
derivative, committed, labelled `kind: demo_fixture`, with its own manifest and its own real
checksums. It exists so `make demo` can run the real seed-and-verify path instead of the
schema-only one, and so the warehouse a reader builds returns numbers rather than empty relations.

Written with pyarrow rather than DuckDB `COPY` so every column keeps the exact Arrow type the
extraction produced: verify_snapshot.py compares column types, and sources.yml is generated from
those types.

    python -m scripts.make_demo_fixture       # or: make demo_fixture
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from scripts.snapshot_layout import snapshot_id

REPO_ROOT = Path(__file__).resolve().parent.parent
CHUNK = 1024 * 1024

# Only the four fact-shaped tables are reduced. The other 17 total under a megabyte and are kept
# whole on purpose: a fixture whose foreign keys resolve because the dimension was filtered to
# match is not testing referential integrity, it is hiding the absence of it.
ORDERS = "sales__orders"
ORDER_LINES = "sales__order_lines"
INVOICES = "sales__invoices"
TRANSACTIONS = "warehouse__stock_item_transactions"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def sorted_by_first_column(table: pa.Table) -> pa.Table:
    """Impose a row order so regenerating the fixture reproduces it byte for byte.

    The extraction cannot promise this -- SQL Server guarantees no order without ORDER BY, and five
    of the 21 tables came back reordered when that was re-measured. The fixture can, because it
    imposes one.
    """
    return table.sort_by([(table.schema.names[0], "ascending")])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir", default="data/raw")
    p.add_argument("--source-manifest", default="data/snapshots/manifest.json")
    p.add_argument("--output-dir", default="data/demo")
    p.add_argument(
        "--from-date",
        default="2018-01-01",
        help="orders on or after this date are kept; the fact tables follow the orders",
    )
    args = p.parse_args()

    in_dir = REPO_ROOT / args.input_dir
    out_dir = REPO_ROOT / args.output_dir
    src_manifest_path = REPO_ROOT / args.source_manifest

    if not src_manifest_path.exists():
        sys.exit(f"{src_manifest_path} is missing -- nothing to derive a fixture from")
    source = json.loads(src_manifest_path.read_text(encoding="utf-8"))

    missing = [n for n in source["tables"] if not (in_dir / f"{n}.parquet").exists()]
    if missing:
        sys.exit(
            f"{in_dir} is missing {len(missing)} of the snapshot's tables ({', '.join(missing[:3])}"
            f"{'...' if len(missing) > 3 else ''}) -- run `make extract` on a machine with the source"
        )

    cutoff = pa.scalar(datetime.fromisoformat(args.from_date).date(), type=pa.date32())

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

    tables: dict[str, dict] = {}
    for name in source["tables"]:
        table = reduced.get(name) or pq.read_table(in_dir / f"{name}.parquet")
        table = sorted_by_first_column(table)
        dest = out_dir / f"{name}.parquet"
        pq.write_table(table, dest, compression="snappy")

        written = pq.ParquetFile(dest)
        tables[name] = {
            "file": dest.name,
            "row_count": written.metadata.num_rows,
            "size_bytes": dest.stat().st_size,
            "sha256": sha256(dest),
            "columns": {f.name: str(f.type) for f in written.schema_arrow},
        }

        expected = source["tables"][name]["columns"]
        if tables[name]["columns"] != expected:
            drifted = [c for c in expected if expected.get(c) != tables[name]["columns"].get(c)]
            sys.exit(
                f"{name}: the fixture's column types differ from the snapshot's ({', '.join(drifted)})"
                " -- sources.yml is generated from the snapshot's types, so the two must agree"
            )

    # The `demo-` prefix gives the fixture its own bronze prefix, so seeding it can never overwrite a
    # published snapshot. The timestamp is the source's rather than the wall clock's, so the fixture
    # derived from one snapshot always carries one id.
    manifest = {
        "schema_version": source["schema_version"],
        "snapshot_timestamp": source["snapshot_timestamp"],
        "snapshot_id": f"demo-{snapshot_id(source['snapshot_timestamp'])}",
        "kind": "demo_fixture",
        "derived_from": source["snapshot_id"],
        "orders_from_date": args.from_date,
        "mssql_version": source["mssql_version"],
        "delivery_time_form": source["delivery_time_form"],
        "table_count": len(tables),
        "total_size_bytes": sum(t["size_bytes"] for t in tables.values()),
        "total_row_count": sum(t["row_count"] for t in tables.values()),
        "tables": tables,
    }

    out = out_dir / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    mb = manifest["total_size_bytes"] / 1048576
    print(f"{out}: {len(tables)} tables, {manifest['total_row_count']:,} rows, {mb:.2f} MB")
    # Built before the f-string rather than inside it: nesting the same quote three deep parses
    # only on 3.12+, and this file is not the place to raise the floor for the whole project.
    reduced_counts = ", ".join(f"{name} {tables[name]['row_count']:,}" for name in reduced)
    print(f"  reduced: {reduced_counts}")
    print(f"  snapshot_id: {manifest['snapshot_id']} (derived from {manifest['derived_from']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
