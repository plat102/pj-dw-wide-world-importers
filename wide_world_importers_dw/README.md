# wide_world_importers_dw

The dbt project. Models over the lake's `raw` schema, built into the `stg`, `dwh` and `mart` schemas of that same lake. Run it from the repository root, not from here — the Makefile passes `--project-dir` and the profile, and the build needs environment variables that `.env` holds.

```bash
make build         # build against whatever is in raw
make parse         # Jinja and YAML errors only, no database work
make catalog       # regenerate docs/data_warehouse_catalog.md from schema.yml + the lake
```

## Layout

| Path                   | Schema        | Materialisation | Holds                                            |
| ---------------------- | ------------- | --------------- | ------------------------------------------------ |
| — (written by dlt)     | `raw`      | table           | one table per entry in `src/ingestion/tables.yml` |
| `models/staging/`      | `staging`    | view            | one view per raw table: renames only          |
| `models/intermediate/` | `staging`    | view            | joins reused by more than one downstream model   |
| `models/marts/core/`   | `core`        | table           | the star: the dimensions and `fct_sales_order_line` |
| `models/marts/sales/`  | `marts`       | table           | `obt_sales_order_line`, columns under contract   |

## Where raw comes from

`models/sources.yml` is hand-written and small. Raw is a schema of the same DuckLake catalog this project writes to, so `{{ source('wwi_raw', 'sales__orders') }}` resolves to `lake.raw.sales__orders` — an ordinary relation, not a `read_parquet` glob. The source names no bucket and no prefix; the profile names the catalog, and dlt decides what lands in it.

Column types are not repeated there. The catalog knows them, and `src/ingestion/tables.yml` is where the column contract is declared and checked against the source database. A unit test fails when the two files stop naming the same set of tables.

`../profiles.yml` is the profile, and `make` points dbt at it with `--profiles-dir`. It reads everything from the environment, so there is nothing to fill in. Do not keep a copy in this directory: `dbt` invoked by hand, without the flag, would read it instead, and a second copy is what drifts. That is why it is git-ignored.

## Tests

Run by `dbt build`. Beyond the key and `relationships` tests in `schema.yml`, every staging model carries `matches_source_rowcount` — staging only renames and casts, so a count differing from its raw table means a silent filter or a source pointed at the wrong schema. The singular tests in `tests/` check invariants rather than columns: the mart holding the fact's grain, and `dim_date`'s calendar arithmetic at the fiscal year boundary, a weekend, and an ISO week that belongs to the next year.

The project depends on no dbt packages. `dbt_utils` was here for one call, `generate_surrogate_key` in `dim_stock_item`, and left with it; `packages.yml` is one file away if a macro is ever worth the dependency.

`macros/processed_at.sql` reads dlt's `_dlt_load_id` — the unix timestamp of the load that wrote the row — rather than calling `current_timestamp`, which is what makes two builds of one load comparable; see `make compare`.
