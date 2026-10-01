---
name: add-source-table
description: Bring a new Wide World Importers source table into the lake's raw schema and give it a staging model, keeping tables.yml, __sources.yml, raw_schema.sql and the model in one change. Use when a model needs a table raw does not carry yet, or the user asks to add, extract or load a source table.
---

# Add a source table

Raw carries exactly the tables a model reads, so a table is added together with the staging model that reads it, in one commit. Three files name the set and tests compare them: `src/ingestion/tables.yml` (what is extracted), `wide_world_importers_dw/models/staging/wide_world_importers/__sources.yml` (what dbt reads) and `src/ingestion/raw_schema.sql` (the raw schema as types, which `make build_empty` and CI build from).

## Steps

1. **Declare the extraction.** Add an entry to `src/ingestion/tables.yml`, following the entries already there:
   - `source`: `Schema.Table` as SQL Server names it, e.g. `Purchasing.PurchaseOrders`.
   - `output`: `<schema>__<table>` in snake_case, e.g. `purchasing__purchase_orders`.
   - `columns`: listed by name, never `*`. Take them from the source table and leave out the ones no model will read.

2. **Declare the dbt source.** In `__sources.yml`, add the same `output` name under `wwi_raw` with `data_tests: [complete_dlt_load]`, like every other table there. `make test` now checks the two files name the same set (`tests/unit/test_source_contract.py`).

From here until step 4, `make check` is red: `tests/unit/test_raw_schema.py` and `make build_empty` see a table in `tables.yml` that `raw_schema.sql` does not have. That is expected. If the user does not want `make extract` run now, stop here and leave the work uncommitted — it cannot land without the load.

3. **Load it — ask the user first.** `make extract` reads the source database with the credential in `.env`, and only the user can say it may run now. It needs `make up` and a reachable SQL Server. It checks that every declared column exists at the source and compares landed row counts against `COUNT(*)`.

4. **Regenerate the raw schema.** `make raw_schema`, then read `git diff src/ingestion/raw_schema.sql`: the new table should be the only change, and its column types are what dlt landed. Never write this file by hand; the hook refuses it.

5. **Write the staging model** `models/staging/wide_world_importers/stg_<schema>__<entity>.sql`, entity plural, modelled on `stg_sales__orders.sql`:
   - one `raw` CTE selecting `*` from `{{ source('wwi_raw', '<output>') }}`;
   - renames only: no joins, no filters, no casts unless the source type is wrong;
   - `<entity>_id` becomes `<entity>_key`; a moment becomes `<name>_at`; a boolean is named `is_<name>`;
   - end with `{{ processed_at() }} as processed_at`;
   - lowercase SQL, leading commas, one column per line.

6. **Document and test it** in `_wide_world_importers__models.yml`: a description ending "One view over `raw.<output>`: renames only -- no joins, no casts, no filter.", and `matches_source_rowcount` with `source_relation: "{{ source('wwi_raw', '<output>') }}"`, as on every other staging model.

7. **Prove it.** `make check` (includes `build_empty`), then `make build` against the loaded lake. Break `matches_source_rowcount` once — add `where false` to the model — and watch it fail before trusting it; then restore.

8. **Regenerate the catalog** with `make catalog` if the model is published downstream, and commit everything above together.

## Do not

- Add a table no model reads yet.
- Put a row count of the new table into any doc or description; `make shape` reports it.
