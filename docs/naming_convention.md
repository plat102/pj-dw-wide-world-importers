# Naming Conventions

Naming standards and code style guidelines for consistency across the project

## dbt Models

> File naming and folder organization standards for dbt models

### File Naming

| Layer                 | Prefix    | Materialization | Example                       |
| --------------------- | --------- | --------------- | ----------------------------- |
| Staging               | `stg_`  | View            | `stg_sales_customer.sql`    |
| Intermediate          | `int_`  | View            | `int_city_flattened.sql` |
| Analytics (Dimension) | `dim_`  | Table           | `dim_customer.sql`          |
| Analytics (Fact)      | `fact_` | Table           | `fact_sales_order_line.sql` |
| Marts                 | `mart_` | Table           | `mart_sales_order_line.sql` |

### Model Organization

```
models/
├── staging/
│   └── wide_world_importers/
│       ├── sales/               # Grouped by source schema
│       ├── warehouse/
│       └── application/
├── intermediate/               # Joins reused by more than one model
├── analytics/
│   ├── dim_*.sql               # Dimension tables
│   └── fact_*.sql              # Fact tables
└── marts/
    └── sales/                  # Grouped by business domain
```

## Database Objects

Naming conventions for tables and columns in the warehouse

### Tables

| Type      | Convention                    | Example                              |
| --------- | ----------------------------- | ------------------------------------ |
| Dimension | Singular, snake_case          | `dim_customer`, `dim_stock_item` |
| Fact      | Plural noun or process name   | `fact_sales_order_line`            |
| Staging   | `stg_` prefix + source name | `stg_sales_customer`               |

### Columns

| Type               | Convention                 | Example                                            |
| ------------------ | -------------------------- | -------------------------------------------------- |
| Primary Key        | `<table>_key`            | `customer_key`, `stock_item_key`               |
| Foreign Key        | `<referenced_table>_key` | `customer_key`, `order_date_key`               |
| Date Surrogate Key | `<description>_date_key` | `order_date_key`, `expected_delivery_date_key` |
| Boolean            | `is_<description>`       | `is_employee`, `is_on_credit_hold`             |
| Surrogate Key      | `<table>_sk`             | `stock_item_sk`                                  |
| General            | snake_case                 | `customer_name`, `unit_price`                  |

**Known exceptions**, recorded rather than quietly tolerated:

| Column | Problem | Why it stays |
|---|---|---|
| `dim_date.day_is_weekday` | `is_` prefix on a 0/1 `integer`, not a boolean | The mart publishes it under an enforced contract |
| ~~`quantiy_per_outer`~~ | Misspelled staging alias over a correctly-spelled source column | Fixed — nothing used it

### Schemas

The warehouse is a DuckLake lakehouse — Parquet on the object store, catalog in Postgres — and
the layers are schemas inside its one catalog.

| Schema      | Purpose                                       |
| ----------- | --------------------------------------------- |
| —           | Raw Parquet on the object store under `bronze/<snapshot-id>/`, read in place |
| `main_stg`  | Staging (`stg_`) and intermediate (`int_`)     |
| `main_dwh`  | Dimensional models                            |
| `main_mart` | Business-ready denormalised tables            |

`wwi_raw` / `wwi_stg` / `wwi_dwh` / `wwi_mart` were the BigQuery dataset names. That build is
frozen; these are not the names in use.

## SQL Style Guide

> SQL formatting standards for readability and maintainability

### Keywords & Formatting

- **Lowercase** for SQL keywords: `select`, `from`, `where`, `join`, `as`
- **Leading commas**: the comma opens the line, aligned under the first column
- **One column per line** in `select`
- **Indentation**: 4 spaces for nested blocks

```sql
select
    customer_key
    , customer_name
    , credit_limit
from dim_customer
```

Leading commas earn their keep: commenting a column out of a wide `select` is a one-character edit
and cannot leave a dangling comma behind, which matters when the widest model has 70 columns.

### Joins

- Align `on` with table name
- Use explicit join types (`left join`, `inner join`)

```sql
select
    c.customer_name
    , o.order_date
from dim_customer as c
left join fact_sales_order_line as o
    on c.customer_key = o.customer_key
where c.is_on_credit_hold = false
```

### CTEs (Common Table Expressions)

- Use descriptive names explaining the transformation
- Separate CTEs with blank lines
- Final CTE before main SELECT

```sql
with customer_orders as (
    select
        customer_key
        , count(*) as order_count
    from fact_sales_order_line
    group by customer_key
),

high_value_customers as (
    select customer_key
    from customer_orders
    where order_count > 10
)

select *
from high_value_customers
```

## dbt Conventions

> Best practices for using dbt features (sources, refs, configs, tests)

### Sources

- Define in `sources.yml` with schema and table name
- Reference using `{{ source('schema_name', 'table_name') }}`

### References

- Use `{{ ref('model_name') }}` for all model dependencies
- Enables dbt lineage tracking

### Configuration

- Set materialization in `dbt_project.yml` by folder
- Override in individual models only when necessary

### Numbers in documentation and comments

**Do not write a row count into a document, a model comment, or a YAML description.** It goes stale
the moment the data span changes, in places nobody remembers to look, and competes with the
warehouse as a source of truth.

The line to hold:

| Changes when… | Examples | Rule |
| --- | --- | --- |
| the **data** changes | row counts, byte sizes, "402 of 686", extraction wall clock | Keep out. State the property, name the command |
| the **code** changes | column counts, model counts, "ten foreign keys" | Fine to write. A reviewer sees them move in the same diff |
| never — it is a pinned expectation | the eight dates in `assert_dim_date_calendar` | Required. That is what the test *is* |

Write "no stock item has ever had more than one distinct price", not "444 rows over 227 items with
zero price changes". The first survives a bigger dataset.

Where a reader wants numbers, give the command:

- `make shape` — every relation with its row and column count
- `make verify` — the snapshot against the manifest's counts and checksums
- `data/snapshots/manifest.json` — authoritative for source row counts, sizes and types

This rule covers documentation describing the *present*. A dated measurement is a different thing
and should carry its numbers — a stale number there is history, not a false claim.

### Testing

- Generic tests go in the `schema.yml` beside the models they cover, one per layer directory.
- Every dimension key carries `unique` and `not_null`; every foreign key on the fact carries
  `relationships`. That is a rule, not a target — a new key without both is incomplete.
- Singular tests go in `tests/`, named `assert_<what_must_be_true>.sql`. Three exist:
  `assert_dim_date_calendar`, `assert_staging_matches_manifest`, `assert_mart_keeps_fact_grain`.
- **A test is not trusted until it has been seen to fail.** Break the thing it guards, watch it go
  red, put it back. A test that has only ever been green says nothing about whether it works, and
  in this project one negative test passed for the wrong reason until it was provoked properly.
- The mart's column list is a contract (`contract: enforced`) — a test in a different shape, which
  fails the build rather than a test run.
