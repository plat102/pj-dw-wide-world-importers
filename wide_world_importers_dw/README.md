# wide_world_importers_dw

The dbt project. Models over a Parquet snapshot on the object store, built into a DuckLake lakehouse. Run it from the repository root, not from here — the Makefile passes `--project-dir` and the profile, and the build needs environment variables that `.env` holds.

```bash
make deps          # install dbt packages (dbt_utils); dbt_packages/ is git-ignored
make build         # build against whatever is in bronze
make parse         # Jinja and YAML errors only, no database work
```

## Layout

| Path                   | Schema        | Materialisation | Holds                                            |
| ---------------------- | ------------- | --------------- | ------------------------------------------------ |
| `models/staging/`      | `main_stg`    | view            | one view per source table: renames and casts     |
| `models/intermediate/` | `main_stg`    | view            | joins reused by more than one downstream model   |
| `models/analytics/`    | `main_dwh`    | table           | the star: the dimensions and `fact_sales_order_line` |
| `models/marts/`        | `main_mart`   | table           | `mart_sales_order_line`, columns under contract    |

## Two generated or environment-driven files

`models/sources.yml` is **generated** — it is a projection of `data/snapshots/manifest.json`. Do not hand-edit it; run `make sources` after an extraction, and `make sources_check` fails CI when the two have drifted. Each source table is addressed as a glob, `<table>/*.parquet`, because dlt decides how many files a table takes.

`profiles.yml` reads everything from the environment, so there is nothing to fill in. `SNAPSHOT_ID` selects which snapshot under `bronze/` the models read; unset, it defaults to the one the manifest names.

## Tests

Run by `dbt build`. Beyond the key and `relationships` tests in `schema.yml`, the singular tests in `tests/` check invariants rather than columns: staging row counts against the manifest, the mart holding the fact's grain, and `dim_date`'s calendar arithmetic at the fiscal year boundary, a weekend, and an ISO week that belongs to the next year.

`macros/snapshot_processed_at.sql` reads the snapshot's timestamp from the manifest rather than calling `current_timestamp`, which is what makes two builds of one snapshot comparable — see `make compare`.
