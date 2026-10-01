---
name: add-dbt-model
description: Add or change a dbt model in wide_world_importers_dw (staging, intermediate, dimension, fact or mart) with the naming, SQL style, tests and docs this project requires. Use when the user asks for a new model, dimension, fact, mart column or a change to one.
---

# Add or change a dbt model

The rules live in `docs/naming_convention.md`; this is the order to apply them in. If the model needs a table raw does not carry, do `add-source-table` first.

## 1. Place it

| Layer | Folder | Name | Built as | Schema |
|---|---|---|---|---|
| Staging | `models/staging/wide_world_importers/` | `stg_<source_schema>__<entity>` (plural) | view | `staging` |
| Intermediate | `models/intermediate/` | `int_<entity>__<verb>` | view | `staging` |
| Dimension | `models/marts/core/` | `dim_<entity>` (singular) | table | `core` |
| Fact | `models/marts/core/` | `fct_<process>` | table | `core` |
| Mart | `models/marts/<domain>/` | `obt_<process>` | table | `marts` |

Materialisation and schema come from `dbt_project.yml` by folder; add a `{{ config() }}` only when the model really differs. An intermediate model exists only when more than one downstream model reuses the join.

## 2. Write the SQL

- Lowercase keywords, leading commas, one column per line, four-space indents, explicit join types, `on` indented under its join.
- Every `ref` in a `from` or `join` gets an alias and every column is qualified with it, e.g. `from {{ ref('stg_sales__customers') }} as stg_sales__customers`. Without the alias `make build_empty` fails: under `--empty` a ref renders as an unnamed subquery.
- Keys are `<table>_key`, date keys `<description>_date_key` (yyyymmdd integer), booleans `is_<description>`. Dimensions are keyed on the natural key; there are no surrogate keys (see `docs/project_roadmap.md`, Change tracking).
- No `current_timestamp`: `processed_at` comes from `{{ processed_at() }}`, which keeps two builds of one load identical (`make compare`).

## 3. Test it

Tests go in the layer's YAML beside the model (`_<layer>__models.yml`):

- every dimension key: `unique` and `not_null`;
- every foreign key on a fact: `relationships` to its dimension;
- every staging model: `matches_source_rowcount` against its raw table;
- the fact and the mart: `not_empty`;
- a property that is not a column test: a singular test `tests/assert_<what_must_be_true>.sql`; a model `--empty` leaves whole, such as `dim_date`, is read there as `{{ ref('dim_date').render() }}`;
- logic whose output you can state by hand: a dbt unit test in `_<layer>__unit_tests.yml` — CI runs these.

Then make each new test fail once on purpose and restore it. A test only ever seen green proves nothing.

## 4. Document it

A `description` on the model and each column, saying what a row is and where the value comes from. Reuse `{{ doc('...') }}` from `models/_docs.md` for an attribute described in more than one place. No row counts, no counts of anything.

Changing a column of `obt_sales_order_line` means changing its enforced contract in `models/marts/sales/_sales__models.yml` in the same commit — name, `data_type` and order.

## 5. Prove it

```bash
make parse        # Jinja and YAML
make build_empty  # every model and test on an empty raw: SQL, contract and unit tests
make check        # the full gate
```

With the stack up and raw loaded: `make build` for the data tests, then `make catalog` to regenerate `docs/data_warehouse_catalog.md` — never edit that file by hand.
