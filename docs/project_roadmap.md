# Project Roadmap

Business context, objectives, current status, and future direction of the data warehouse project

**Project Type**: Learning Project `<br>`
**Where it stands**: Sales Order star schema built and tested, running on DuckDB over a
checksummed Parquet snapshot `<br>`
**Next**: move the snapshot onto object storage; then supply-chain facts

> This file describes **state**, not numbered phases. It used to call the DuckDB re-platform
> "Phase 2: Infrastructure Automation" while the project plan meant something else by Phase 2, and
> two documents numbering the same phases differently is worse than neither doing it. Phase
> numbering belongs to the project plan; this file says what is true.

---

## 📊 Business Context

Wide World Importers relies on an OLTP database optimized for transactions, creating analytical challenges:

- **Performance bottleneck**: Analytical queries slow down operational systems
- **Complex data access**: Business insights require joining 10+ normalized tables
- **No historical tracking**: Cannot analyze trends or changes over time
- **IT dependency**: Business users wait days for custom reports

**Business Impact:** Delayed decision-making, missed sales opportunities, inability to forecast accurately

---

## 🎯 Objective

Build a modern cloud-based data warehouse to enable self-service analytics and data-driven decision making.

**Primary Goals:**

1. Implement a dimensional model optimized for sales analytics
2. Establish a scalable ELT pipeline using modern data stack
3. Enable business users to create their own reports via BI tools
4. Demonstrate best practices in data warehouse design and implementation

**Target Users:**

- Sales managers analyzing performance by customer, product, and time period
- Operations team monitoring order fulfillment and delivery metrics
- Executives tracking KPIs and business trends

## ☑️ Success Criteria

A ✅ here means there is a command whose output shows it. Anything without one is 🚧, however
confident it feels.

### Functional Requirements

- ✅ **Data completeness** — every staging model's row count matches the manifest exactly.
  `make build` runs `assert_staging_matches_manifest` over all 15 of them; `make verify` checks the
  Parquet's SHA256. `make shape` prints the current counts.
- ✅ **Accuracy** — every extracted table's row count matches the source count, 0 discrepancies
  over all 21. Same two commands.
- ✅ **Referential integrity** — ten `relationships` tests from the fact, plus `unique` and
  `not_null` on every dimension key. `make build`.
- ✅ **Flexibility** — `mart_sales_order_line` is one table, 70 columns, no join needed. Its shape
  is declared under `contract: enforced`.
- 🚧 **Performance** — "dashboard queries under 5 seconds" was never measured, and the dashboard it
  referred to points at the frozen BigQuery build. What *is* measured is the build, and it sits
  comfortably inside the 60-second budget CI will hold it to.

### Technical Requirements

- ✅ **Reproducibility** — two builds of one snapshot produce identical output. 26 relations
  compared, 0 differing: `make compare`. Two extractions of the same source produce byte-identical
  Parquet.
- ✅ **Maintainability** — transformations are SQL in version control, and every documented claim
  carries the command that shows it.
- 🚧 **Scalability** — the snapshot already carries 21 tables, including the six the supply-chain
  facts need, so the *data* is there. No second business process has been built, so the claim that
  the architecture supports one is a design argument rather than a demonstration.
- 🚧 **Data quality** — 50 tests exist and each was seen to fail before it was trusted. Still no
  Great Expectations suite and no CI, so nothing enforces them on a pull request.
- 🚧 **Automation** — none. `make` is the orchestrator and a human runs it.
- ❌ **Cost efficiency as a cloud property** — no longer applicable. The warehouse is a local
  DuckDB file and costs nothing, which is a different claim from the one this line used to make.

## 📋 Project Scope

### In Scope

- **Business Process**: Sales Order (order processing, fulfillment, delivery)
- **Data Sources**: Wide World Importers OLTP database
- **Deliverables**:
  - Dimensional data warehouse (star schema)
  - BI dashboards for sales performance analysis
  - Complete technical documentation
- **Technology**: dbt on DuckDB over a Parquet snapshot. The BigQuery build is frozen as an exhibit.

SCD Type 2 was listed here as a deliverable and is **not built**. See "Change tracking" below for
the one position this project holds on it.

### Out of Scope

- Real-time data ingestion
- Advanced data science/ML capabilities
- Production-grade orchestration and monitoring

## 🚀 Where it stands

Each claim below is followed by the command that shows it. Anything without one is a plan.

### Built

- **Sales Order star schema on DuckDB.** 26 models, `dbt build` green: `make build`.
- **Reproducible extraction.** 21 tables, 277 columns, out of a frozen database snapshot in under
  a minute. Two runs of the same source produce byte-identical Parquet: `make extract`.
- **A snapshot contract.** SHA256, row count and column type per table in
  `data/snapshots/manifest.json`: `make verify`.
- **50 dbt tests.** Keys, ten referential tests from the fact, manifest row-count parity, a mart
  grain test, a calendar test: `make build`.
- **A deterministic build.** Two builds, every relation compared, none differing: `make compare`.
- **An enforced contract on the mart.** 70 columns and their types declared; an upstream change
  that would alter the shape fails the build.
- **Looker Studio dashboards** — against the frozen BigQuery build, not against DuckDB.

### Not built

- **Ingestion is manual into the warehouse.** The extraction produces Parquet on local disk;
  moving it to object storage is the next piece of work.
- **No CI.** There is no `.github/`, so nothing checks a pull request. Blocked on the object store,
  which CI needs as a service container.
- **One business process.** Sales only. Purchasing, inventory and fulfilment are designed, not built.
- **No orchestration.** `make` is the orchestrator.
- **No incremental models.** Everything is a full rebuild, which currently costs seconds.

### Change tracking

**This project holds one position on SCD Type 2, and it is this one.** Earlier drafts of this file
held three at once — a delivered deliverable, a current limitation, and a long-term ambition.

Every dimension is **Type 0**: a change overwrites. `dim_stock_item` carries a surrogate key,
`stock_item_sk`, so a Type 2 build can later give one item several rows; no other dimension has one.

The key was introduced to version `unit_price`, and that turned out to be the wrong reason. The
source table is system-versioned and its archive is not empty, but **no stock item has ever had
more than one distinct price** — the only column that ever changes is a JSON tag blob — and the data
generator never writes to that table at all, so extending the data cannot create history either.
The key stays because it costs nothing.

Two dimensions do change, and only two: **`Application.People` and `Sales.Customers`**, on a
minority of their rows each. Every other temporal dimension is unchanged, `Warehouse.StockItems`
included. So SCD2 has a real subject, just not the product dimension. Building it needs the two
`*_Archive` tables added to the extraction contract first, which bumps `schema_version` and
requires a fresh snapshot. Until that happens SCD2 is not on the near list.

## 🗺️ What comes next

In order, because each depends on the one before.

1. **The snapshot moves to object storage**, addressed as `s3://`, with an open table format above
   it. This is what a real platform's storage layer looks like and the local filesystem is not.
2. **CI on every pull request** — the object store and catalog as service containers, snapshot
   verification, then `dbt build`. It must be shown to go red as well as green.
3. **Supply-chain facts**: purchasing, inventory movement, order fulfilment. Conformed dimensions
   are already in the snapshot for these; the extraction pulled 21 tables, not the 15 the sales
   star needs.
4. **SCD Type 2**, on a dimension that changes, once the archive tables are in the contract.

Not planned: real-time ingestion, ML, production orchestration.

### Risks & Mitigation

| Risk                        | Impact              | Mitigation                                                     |
| --------------------------- | ------------------- | -------------------------------------------------------------- |
| **Source system changes**   | Breaking pipeline   | The manifest pins column types and the engine version, so a rebuild that disagrees fails rather than drifting |
| **Documentation drifts from code** | Loss of trust | Every claim carries the command that shows it; a claim that cannot be run gets deleted |
| **Data quality issues**     | Incorrect analytics | 50 tests in the build, each one shown to fail before it was trusted |
| **A silent non-determinism**| Unreproducible results | `make compare` builds twice and names the column that differs |
| **Scope creep**             | Delayed delivery    | One business process at a time, and the next step is always the one the others depend on |

## 🔌 Extension Path

The architecture is designed for extensibility. Adding new business processes follows a repeatable pattern.

### Future Business Processes

The architecture is designed to support additional business processes with minimal rework. Each new process follows the same pattern: **source → staging → analytics → marts**

**Potential Extensions:**

- **Purchase Order analytics**: Procurement metrics, supplier performance
- **Inventory management**: Stock movements, turnover, valuation
- **Customer intelligence**: Lifetime value, segmentation, churn prediction

**New Dimensions (as needed):**

- Dim tables for procurement analytics
- Dim tables for inventory location analysis
- Additional conformed dimensions shared across business processes

---
