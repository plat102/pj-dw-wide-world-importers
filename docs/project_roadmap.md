# Project Roadmap

**Type**: Learning project **Where it stands**: Sales Order star schema on a DuckLake lakehouse whose raw layer dlt loads into the same catalog, with CI on every pull request **Next**: supply-chain facts, then tests on the staging layer

> This file describes **state**, not numbered phases. Nothing in this repository numbers phases; it says what is true instead.

## Business context

WWI runs on an OLTP database optimized for transactions:

- Analytical queries slow down operational systems
- Business insight needs joins across 10+ normalized tables
- No historical tracking, so no trend analysis
- Business users wait days for custom reports

**Objective**: a dimensional warehouse enabling self-service analytics for sales managers, operations and executives.

## Success criteria

A ✅ means there is a command whose output shows it. Anything without one is 🚧, however confident it feels.

| | Criterion | Evidence |
|---|---|---|
| ✅ | **Data completeness** | Every raw table holds one complete load, or nothing is built: `make build` runs `complete_dlt_load` first. Every staging model's row count matches the raw table it reads (`matches_source_rowcount`) |
| ✅ | **Accuracy** | Every declared column is checked to exist in the source before the load. A login that row-level security hides rows from is refused (`COUNT(*)` against `sys.partitions`), and every table's landed row count is compared against the source, read back through an attach of the extraction's own. `make extract` |
| ✅ | **Referential integrity** | A `relationships` test on every foreign key from the fact, `unique` + `not_null` on every dimension key. `make build` |
| ✅ | **Flexibility** | `obt_sales_order_line` is one table, no join needed, its shape declared under `contract: enforced` |
| ✅ | **Reproducibility** | Two builds of one raw load, every relation compared, 0 differing: `make compare` |
| ✅ | **Maintainability** | Transformations are SQL in version control; every claim carries its command |
| ✅ | **Data quality** | Every test seen to fail before it was trusted: `make build`. CI runs every one of them on an empty raw schema, which checks the SQL and the logic; the ones about the data itself need `make extract` — see **Automation** below |
| 🚧 | **Performance** | "Dashboard queries under 5 seconds" was never measured, and that dashboard points at the frozen BigQuery build. The build's own wall clock is what is measured |
| 🚧 | **Scalability** | Adding a business process means adding its tables to the extraction contract and its models in the same change. No second business process exists, so this is a design argument, not a demonstration |
| 🚧 | **Automation** | CI runs `make check` on every pull request, which builds every model, data test and dbt unit test on an empty raw schema: a misspelt column or a broken contract fails before merge. The data itself is loaded from a source CI has no access to, so the end-to-end build still runs on a developer machine. Nothing runs on a schedule and no orchestrator owns the extraction |
| ❌ | **Cost efficiency as a cloud property** | No longer applicable — the warehouse runs on containers this repository starts and throws away |

Two extractions of one source agree on row counts and column sets but **not on physical row order**: the source is read without `ORDER BY`, and that was measured, not assumed. So comparing two raw loads byte for byte cannot answer "did the source change". Imposing a sort key before the write would fix that; it is not done.

## Scope

**In**: Sales Order (processing, fulfillment, delivery), from the WWI OLTP database. dbt on DuckLake, raw included; the BigQuery build is a frozen exhibit.

**Out**: real-time ingestion, ML, production orchestration and monitoring.

SCD Type 2 was once listed as a deliverable and is **not built** — see [Change tracking](#change-tracking).

## Where it stands

### Built

| What | Shown by |
|---|---|
| Sales Order star schema | `make build` |
| Extraction of every declared table straight to the object store, in one dlt run | `make extract` |
| An extraction contract — which tables and columns raw must carry | `src/ingestion/tables.yml`, checked by `make check` and `make extract` |
| dbt tests: dimension keys, referential integrity, raw row-count parity, mart grain, calendar arithmetic | `make build` |
| A deterministic build | `make compare` |
| An enforced contract on the mart's columns | `make build` |
| The `raw` schema of the lake, one table per declared source table | `make extract` |
| Static gates on every pull request: lint, import contracts, types, unit tests, dbt compile | `.github/workflows/build.yml` |
| Enforced architectural boundaries, as import contracts | `make lint` |
| Looker Studio dashboards | against the frozen BigQuery build |

### Not built

- **One business process.** Sales only; purchasing, inventory and fulfilment are designed, not built.
- **No orchestration.** `make` is the orchestrator and a human runs it.
- **No incremental models.** Everything is a full rebuild, which currently costs seconds. This is also what makes every dimension Type 1 — see [Change tracking](#change-tracking).
- **Staging has no tests or docs.** No `unique`, no `not_null`, and barely a description between the lot of them.

### Change tracking

**One position on slowly changing dimensions, and it is this one.** Every dimension is **Type 1 — overwrite**, in Kimball's sense: the attribute reflects the most recent assignment and history is destroyed. It is reached by rebuild rather than by `update`: the extraction replaces `raw` and dbt rebuilds the star from it, so there is no place a superseded value could survive. `dim_date` is the exception and is **Type 0 — retain original**: it is generated from a date spine, never loaded from a source.

Nothing in the warehouse is a Type 2 mechanism. There is no dbt snapshot, no model is incremental, and no dimension carries a row effective date, a row expiration date or a current row indicator — the three columns Type 2 requires.

No dimension carries a surrogate key. Every one is keyed on its natural key, renamed to `<entity>_key`. `dim_stock_item` once carried an MD5 hash key held in reserve for a Type 2 build; it was dropped, because nothing joined it and Type 2 means rewiring the star rather than adding a column. `dim_date.date_key` is a `yyyymmdd` integer — a smart key, which is the one dimension Kimball exempts from the surrogate key rule.

Two dimensions do change: **`Application.People` and `Sales.Customers`**, on a minority of rows each. So Type 2 has a real subject, just not the product dimension. The source is SQL Server temporal, so the history already exists in the `*_Archive` tables — building Type 2 here is reading those tables, not running `dbt snapshot`, which could only record changes from the day it first ran.

## What comes next

In order, because each depends on the one before.

1. **Supply-chain facts** — purchasing, inventory movement, order fulfilment. The tables these need (`Purchasing.PurchaseOrders`, `Purchasing.PurchaseOrderLines`, `Warehouse.StockItemTransactions`, `Application.TransactionTypes`, `Sales.Invoices`) go into `tables.yml` in the same change as the models that read them, which needs a fresh extraction.
2. **Tests and documentation on the staging layer** — the largest remaining gap in the dbt project.
3. **SCD Type 2**, on a dimension that changes. The subjects are `Application.People` and `Sales.Customers`, so it is their `*_Archive` tables that the contract needs — not `Warehouse.StockItems_Archive`, the archive of the dimension with no history.

Not planned: real-time ingestion, ML, production orchestration.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Source system changes | Breaking pipeline | Declared columns are checked against the source before every load, and the mart's enforced contract fails a build whose shape moved |
| Documentation drifts from code | Loss of trust | Every claim carries its command; a claim that cannot be run gets deleted |
| Data quality issues | Incorrect analytics | Every test shown to fail before it was trusted |
| Silent non-determinism | Unreproducible results | `make compare` builds twice and names the column that differs |
| Scope creep | Delayed delivery | One business process at a time |

## Extension path

Each new business process follows the same pattern: **raw → staging → core → marts**. Candidates: purchase order analytics (procurement, supplier performance), inventory management (movements, turnover, valuation), customer intelligence (lifetime value, segmentation).
