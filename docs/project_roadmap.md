# Project Roadmap

**Type**: Learning project
**Where it stands**: Sales Order star schema on a DuckLake lakehouse, over a checksummed Parquet
snapshot on object storage, with CI on every pull request
**Next**: supply-chain facts, then tests on the staging layer

> This file describes **state**, not numbered phases. Nothing in this repository numbers phases; it
> says what is true instead.

## Business context

WWI runs on an OLTP database optimized for transactions:

- Analytical queries slow down operational systems
- Business insight needs joins across 10+ normalized tables
- No historical tracking, so no trend analysis
- Business users wait days for custom reports

**Objective**: a dimensional warehouse enabling self-service analytics for sales managers,
operations and executives.

## Success criteria

A ✅ means there is a command whose output shows it. Anything without one is 🚧, however confident
it feels.

| | Criterion | Evidence |
|---|---|---|
| ✅ | **Data completeness** | Every staging model's row count matches the manifest. `make build` runs `assert_staging_matches_manifest` over all 15 |
| ✅ | **Accuracy** | Every extracted table's row count matches the source, 0 discrepancies over all 21. `make verify` |
| ✅ | **Referential integrity** | Ten `relationships` tests from the fact, `unique` + `not_null` on every dimension key. `make build` |
| ✅ | **Flexibility** | `mart_sales_order_line` is one table, 70 columns, no join needed, shape declared under `contract: enforced` |
| ✅ | **Reproducibility** | Two builds of one snapshot, every relation compared, 0 differing: `make compare` |
| ✅ | **Maintainability** | Transformations are SQL in version control; every claim carries its command |
| ✅ | **Data quality** | 44 tests, each seen to fail before it was trusted, all run in CI over the fixture's real rows: `make check`, `make build_demo` |
| 🚧 | **Performance** | "Dashboard queries under 5 seconds" was never measured, and that dashboard points at the frozen BigQuery build. The build's own wall clock is what is measured |
| 🚧 | **Scalability** | The snapshot carries the six tables the supply-chain facts need, so the data is there. No second business process exists, so this is a design argument, not a demonstration |
| 🚧 | **Automation** | CI builds and tests every pull request, but nothing runs on a schedule and no orchestrator owns the extraction |
| ❌ | **Cost efficiency as a cloud property** | No longer applicable — the warehouse runs on containers this repository starts and throws away |

Two extractions of one source agree on row counts and column sets but **not on bytes**: the source
is read without `ORDER BY` and physical row order is not guaranteed. Measured 2026-08-18: 5 of 21
tables came back reordered, same rows.

## Scope

**In**: Sales Order (processing, fulfillment, delivery), from the WWI OLTP database. dbt on DuckLake
over a Parquet snapshot; the BigQuery build is a frozen exhibit.

**Out**: real-time ingestion, ML, production orchestration and monitoring.

SCD Type 2 was once listed as a deliverable and is **not built** — see [Change tracking](#change-tracking).

## Where it stands

### Built

| What | Shown by |
|---|---|
| Sales Order star schema, 23 models | `make build` |
| Reproducible extraction, 21 tables, 277 columns, one snapshot-isolation transaction | `make extract` |
| A snapshot contract — SHA256, row count and column types per table | `make verify` |
| 44 dbt tests: keys, ten referential, manifest parity, mart grain, calendar | `make build` |
| A deterministic build | `make compare` |
| An enforced contract on the mart, 70 columns | `make build` |
| The snapshot on object storage under `bronze/<snapshot-id>/` | `make seed_bronze` |
| CI on every pull request, seen red as well as green | `.github/workflows/build.yml` |
| A committed fixture with real rows and real checksums — what CI builds on | `make demo` |
| Enforced architectural boundaries, three import contracts | `make lint` |
| Looker Studio dashboards | against the frozen BigQuery build |

### Not built

- **One business process.** Sales only; purchasing, inventory and fulfilment are designed, not built.
- **No orchestration.** `make` is the orchestrator and a human runs it.
- **No incremental models.** Everything is a full rebuild, which currently costs seconds.
- **Staging has no tests or docs.** 15 models, no `unique`, no `not_null`, one description between them.

### Change tracking

**One position on SCD Type 2, and it is this one.** Every dimension is **Type 0**: a change
overwrites.

`dim_stock_item` carries the only surrogate key, `stock_item_sk`, so a Type 2 build could later give
one item several rows. It was introduced to version `unit_price` and that reason was wrong: **no
stock item has ever had more than one distinct price** — the only column that changes is a JSON tag
blob — and the data generator never writes to that table, so extending the data cannot create
history either. The key stays because it costs nothing.

Two dimensions do change: **`Application.People` and `Sales.Customers`**, on a minority of rows
each. So SCD2 has a real subject, just not the product dimension. Building it needs the two
`*_Archive` tables in the extraction contract first, which bumps `schema_version` and requires a
fresh snapshot.

## What comes next

In order, because each depends on the one before.

1. **Supply-chain facts** — purchasing, inventory movement, order fulfilment. The extraction already
   pulls 21 tables rather than the 15 the sales star needs; the six spare ones are staged for this.
2. **Tests and documentation on the staging layer** — the largest remaining gap in the dbt project.
3. **SCD Type 2**, on a dimension that changes, once the archive tables are in the contract.

Not planned: real-time ingestion, ML, production orchestration.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Source system changes | Breaking pipeline | The manifest pins column types and engine version; a rebuild that disagrees fails rather than drifting |
| Documentation drifts from code | Loss of trust | Every claim carries its command; a claim that cannot be run gets deleted |
| Data quality issues | Incorrect analytics | 44 tests, each shown to fail before it was trusted |
| Silent non-determinism | Unreproducible results | `make compare` builds twice and names the column that differs |
| Scope creep | Delayed delivery | One business process at a time |

## Extension path

Each new business process follows the same pattern: **source → staging → analytics → marts**.
Candidates: purchase order analytics (procurement, supplier performance), inventory management
(movements, turnover, valuation), customer intelligence (lifetime value, segmentation).
