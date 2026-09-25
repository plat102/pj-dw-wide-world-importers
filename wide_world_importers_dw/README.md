# wide_world_importers_dw

The dbt project. Models over the lake's `bronze` schema, built into the `stg`, `dwh` and `mart` schemas of that same lake. Run it from the repository root, not from here — the Makefile passes `--project-dir` and the profile, and the build needs environment variables that `.env` holds.

```bash
make deps          # install dbt packages (dbt_utils); dbt_packages/ is git-ignored
make build         # build against whatever is in bronze
make parse         # Jinja and YAML errors only, no database work
```

## Layout

| Path                   | Schema        | Materialisation | Holds                                            |
| ---------------------- | ------------- | --------------- | ------------------------------------------------ |
| — (written by dlt)     | `bronze`      | table           | one table per entry in `src/ingestion/tables.yml` |
| `models/staging/`      | `main_stg`    | view            | one view per bronze table: renames and casts     |
| `models/intermediate/` | `main_stg`    | view            | joins reused by more than one downstream model   |
| `models/analytics/`    | `main_dwh`    | table           | the star: the dimensions and `fact_sales_order_line` |
| `models/marts/`        | `main_mart`   | table           | `mart_sales_order_line`, columns under contract    |

## Where bronze comes from

`models/sources.yml` is hand-written and small. Bronze is a schema of the same DuckLake catalog this project writes to, so `{{ source('wwi_raw', 'sales__orders') }}` resolves to `lake.bronze.sales__orders` — an ordinary relation, not a `read_parquet` glob. The source names no bucket and no prefix; the profile names the catalog, and dlt decides what lands in it.

Column types are not repeated there. The catalog knows them, and `src/ingestion/tables.yml` is where the column contract is declared and checked against the source database. A unit test fails when the two files stop naming the same set of tables.

`../profiles.yml` is the profile, and `make` points dbt at it with `--profiles-dir`. It reads everything from the environment, so there is nothing to fill in. Do not keep a copy in this directory: `dbt` invoked by hand, without the flag, would read it instead, and a second copy is what drifts. That is why it is git-ignored.

## Tests

Run by `dbt build`. Beyond the key and `relationships` tests in `schema.yml`, every staging model carries `matches_bronze_rowcount` — staging only renames and casts, so a count differing from its bronze table means a silent filter or a source pointed at the wrong schema. The singular tests in `tests/` check invariants rather than columns: the mart holding the fact's grain, and `dim_date`'s calendar arithmetic at the fiscal year boundary, a weekend, and an ISO week that belongs to the next year.

`macros/processed_at.sql` reads dlt's `_dlt_load_id` — the unix timestamp of the load that wrote the row — rather than calling `current_timestamp`, which is what makes two builds of one load comparable; see `make compare`.
