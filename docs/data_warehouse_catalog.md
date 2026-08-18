# Data Warehouse Catalog

Every column below was read out of a built warehouse, not transcribed from a design. Types are
DuckDB types. Reproduce with:

```bash
make up && make build
make shape          # every relation with its row and column count
```

For the column list, attach the lake from any DuckDB session -- the catalog and the store are all
it takes, which is the point of keeping the warehouse there rather than in a local file:

```sql
select table_schema, table_name, column_name, data_type
from information_schema.columns
where table_catalog = 'lake' order by 1, 2, ordinal_position;
```

Row counts are not in this file on purpose — see [Counts](#counts) at the end.

## Schemas

The warehouse is a DuckLake lakehouse -- Parquet on the object store, catalog in Postgres --
built by `dbt build`. Layers are schemas
inside it, not separate datasets.

| Schema       | Layer        | Contents                                                        |
| ------------ | ------------ | --------------------------------------------------------------- |
| —            | Source       | Parquet under `data/raw/`, read in place; nothing is loaded      |
| `main_stg`   | Staging      | One view per source table, plus intermediate joins              |
| `main_dwh`   | Dimensional  | The star schema: dimensions, role-playing views, the fact       |
| `main_mart`  | Mart         | One denormalised table for BI                                   |

The BigQuery datasets `wwi_raw` / `wwi_stg` / `wwi_dwh` / `wwi_mart` were the earlier layout.
They are frozen and are not what this catalog describes.

## Fact table

### `fact_sales_order_line` — 20 columns

One row per sales order line. **Grain**: `sales_order_line_key`, tested `unique` and `not_null`.
Source: `Sales.OrderLines` joined to `Sales.Orders`, with `bill_to_customer_key` resolved from
`Sales.Customers`.

| Column                                        | Type                     | Role     | Notes                                                    |
| --------------------------------------------- | ------------------------ | -------- | -------------------------------------------------------- |
| `sales_order_line_key`                        | BIGINT                   | grain    | `OrderLineID`                                            |
| `sales_order_key`                             | BIGINT                   | degen.   | `OrderID`; the order itself has no dimension             |
| `customer_key`                                | BIGINT                   | FK       | → `dim_customer`                                         |
| `bill_to_customer_key`                        | BIGINT                   | FK       | → `dim_customer`; resolved from the customer, not the order |
| `stock_item_key`                              | BIGINT                   | FK       | → `dim_stock_item`                                       |
| `package_type_key`                             | BIGINT                   | FK       | → `dim_package_type`                                     |
| `salesperson_key`                             | BIGINT                   | FK       | → `dim_person`                                           |
| `picked_by_person_key`                        | BIGINT                   | FK       | → `dim_person`; nullable, an unpicked line has none      |
| `contact_person_key`                          | BIGINT                   | FK       | → `dim_person`                                            |
| `order_date_key`                              | VARCHAR                  | FK       | → `dim_date`; yyyymmdd as text, not an integer           |
| `expected_delivery_date_key`                  | VARCHAR                  | FK       | → `dim_date`; nullable                                    |
| `sales_order_picking_completed_date_key`      | VARCHAR                  | FK       | → `dim_date`; nullable                                    |
| `sales_order_line_picking_completed_date_key` | VARCHAR                  | FK       | → `dim_date`; nullable                                    |
| `backorder_order_key`                         | BIGINT                   | degen.   | The order this one backorders; nullable                  |
| `quantity`                                    | BIGINT                   | measure  | Ordered                                                   |
| `picked_quantity`                             | BIGINT                   | measure  | Picked; less than `quantity` on a short pick             |
| `unit_price`                                  | DECIMAL(18,2)            | measure  | Non-additive per row; weight by quantity                 |
| `tax_rate`                                    | DECIMAL(18,3)            | measure  | Non-additive; a percentage                               |
| `is_undersupply_backordered`                  | BOOLEAN                  | flag     |                                                           |
| `sales_order_line_processed_at`               | TIMESTAMP WITH TIME ZONE | metadata | The snapshot's timestamp, from the manifest — not a clock |

Ten foreign keys carry `relationships` tests. `order_date_key` is `not_null`; the other three
date keys are not, because a line that has not shipped has no delivery or picking date.

## Dimensions

### `dim_customer` — 33 columns

**Grain**: one row per customer. **Type 0**: no history is tracked, and the snapshot carries only
the current version of each row, so there is none to track.

| Column                               | Type          | Notes                                          |
| ------------------------------------ | ------------- | ---------------------------------------------- |
| `customer_key`                       | BIGINT        | `unique`, `not_null`                           |
| `customer_name`                      | VARCHAR       |                                                |
| `bill_to_customer_key`               | BIGINT        | Self-relationship; often the customer itself   |
| `customer_category_name`             | VARCHAR       |                                                |
| `buying_group_key`                   | BIGINT        |                                                |
| `buying_group_name`                  | VARCHAR       | Nullable; most customers belong to none        |
| `primary_contact_full_name`          | VARCHAR       |                                                |
| `primary_contact_is_system_user`     | BOOLEAN       |                                                |
| `primary_contact_is_employee`        | BOOLEAN       |                                                |
| `primary_contact_is_salesperson`     | BOOLEAN       |                                                |
| `primary_contact_phone_number`       | VARCHAR       |                                                |
| `primary_contact_email_address`      | VARCHAR       |                                                |
| `alternate_contact_full_name`        | VARCHAR       |                                                |
| `delivery_method_name`               | VARCHAR       |                                                |
| `delivery_city_key`                  | BIGINT        |                                                |
| `delivery_city_name`                 | VARCHAR       | From `int_city_flattened`                      |
| `delivery_state_province_name`       | VARCHAR       |                                                |
| `delivery_state_province_population` | BIGINT        |                                                |
| `delivery_country_name`              | VARCHAR       |                                                |
| `delivery_country_formal_name`       | VARCHAR       |                                                |
| `delivery_country_type`              | VARCHAR       |                                                |
| `delivery_country_population`        | BIGINT        |                                                |
| `postal_city_key`                    | BIGINT        | Key only; no postal city attributes are carried |
| `credit_limit`                       | DECIMAL(18,2) | **Nullable**, and mostly null — a customer on no limit has none |
| `standard_discount_percentage`       | DECIMAL(18,3) |                                                |
| `is_on_credit_hold`                  | BOOLEAN       |                                                |
| `payment_term_days`                  | BIGINT        |                                                |
| `phone_number`                       | VARCHAR       | The customer's own, not a contact's            |
| `website_url`                        | VARCHAR       |                                                |
| `delivery_address`                   | VARCHAR       | Two source lines concatenated                  |
| `delivery_postal_code`               | VARCHAR       |                                                |
| `postal_address`                     | VARCHAR       | Two source lines concatenated                  |
| `postal_postal_code`                 | VARCHAR       |                                                |

### `dim_stock_item` — 18 columns

**Grain**: one row per stock item today. **Type 0**, with a surrogate key in place for a later
Type 2 build.

| Column                     | Type          | Notes                                                        |
| -------------------------- | ------------- | ------------------------------------------------------------ |
| `stock_item_sk`            | VARCHAR       | Surrogate key, MD5 over the natural key. `unique`, `not_null` |
| `stock_item_key`           | BIGINT        | Natural key. `unique`, `not_null`                            |
| `stock_item_name`          | VARCHAR       |                                                              |
| `supplier_key`             | BIGINT        |                                                              |
| `color_key`                | BIGINT        | **Nullable** — not every item has a colour                   |
| `unit_package_type_name`   | VARCHAR       |                                                              |
| `outer_package_type_name`  | VARCHAR       |                                                              |
| `brand`                    | VARCHAR       | Nullable; most items have none                               |
| `size`                     | VARCHAR       | Free text, not a measure                                     |
| `lead_time_days`           | BIGINT        |                                                              |
| `quantity_per_outer`       | BIGINT        | Was misspelled `quantiy_per_outer` by a staging alias over a correctly-spelled source column; fixed |
| `is_chiller_stock`         | BOOLEAN       |                                                              |
| `tax_rate`                 | DECIMAL(18,3) |                                                              |
| `unit_price`               | DECIMAL(18,2) | The list price. No history exists — see below                |
| `recommended_retail_price` | DECIMAL(18,2) |                                                              |
| `typical_weight_per_unit`  | DECIMAL(18,3) |                                                              |
| `color_name`               | VARCHAR       | Nullable with `color_key`                                    |
| `supplier_name`            | VARCHAR       |                                                              |

`unit_price` has **no history in this data.** The source table is system-versioned and its archive
is not empty, but **no stock item has ever had more than one distinct price** — the only column
that ever changes is a JSON tag blob. The reason is structural rather than incidental: the data
generator never writes to that table at all, so extending the data forward cannot create history
either. The surrogate key is kept because it costs nothing, not because there is history to version.

### `dim_person` — 8 columns

**Grain**: one row per person. Covers system users, employees and salespeople in one dimension;
the fact points at it three times, through the three role-playing views below.

| Column                 | Type    | Notes                |
| ---------------------- | ------- | -------------------- |
| `person_key`           | BIGINT  | `unique`, `not_null` |
| `person_full_name`     | VARCHAR |                      |
| `person_preferred_name`| VARCHAR |                      |
| `is_system_user`       | BOOLEAN |                      |
| `is_employee`          | BOOLEAN |                      |
| `is_salesperson`       | BOOLEAN | True for 10 people   |
| `phone_number`         | VARCHAR |                      |
| `email_address`        | VARCHAR |                      |

### `dim_package_type` — 2 columns

| Column              | Type    | Notes                |
| ------------------- | ------- | -------------------- |
| `package_type_key`  | BIGINT  | `unique`, `not_null` |
| `package_type_name` | VARCHAR |                      |

### `dim_date` — 12 columns

**Grain**: one row per day, 2000-01-01 to 2050-12-31. Generated, not sourced. Pinned by
`tests/assert_dim_date_calendar.sql` over eight dates chosen at the three places the arithmetic
is easiest to get wrong.

| Column           | Type    | Notes                                                              |
| ---------------- | ------- | ------------------------------------------------------------------ |
| `date_key`       | VARCHAR | yyyymmdd as **text**. `unique`, `not_null`                          |
| `full_date`      | DATE    | `unique`, `not_null`                                                |
| `year`           | BIGINT  | Calendar year                                                      |
| `year_week`      | BIGINT  | **ISO year** × 100 + ISO week. Not the calendar year: 2024-12-30 is `202501`, because ISO week 1 of 2025 starts while the calendar still says December |
| `year_day`       | BIGINT  | Calendar year × 1000 + day of year                                 |
| `fiscal_year`    | BIGINT  | April start. April 2024 belongs to fiscal 2025                     |
| `fiscal_qtr`     | VARCHAR | `Q1`–`Q4`, **aligned to the April start**: Q1 is Apr–Jun, Q4 is Jan–Mar. It was the calendar quarter before, which put April in Q2 of a year that begins in April |
| `month`          | BIGINT  | 1–12                                                               |
| `month_name`     | VARCHAR | `January`, …                                                        |
| `week_day`       | BIGINT  | 1 = Sunday … 7 = Saturday. DuckDB's own `dayofweek` is 0-based, so the model adds one to keep this numbering |
| `day_name`       | VARCHAR | `Monday`, …                                                         |
| `day_is_weekday` | INTEGER | **0 or 1, not a boolean** despite the `is_` prefix |

### Role-playing views

`dim_contact_person`, `dim_picked_by_person` and `dim_salesperson_person` are views over
`dim_person` with every column prefixed for its role. 8 columns each. The first two carry every
person; `dim_salesperson_person` filters `is_salesperson` and is much smaller.

They are built and tested but **nothing reads them**: `mart_sales_order_line` joins `dim_person`
directly under three aliases instead. They exist so a BI tool can join a role without aliasing.

## Mart

### `mart_sales_order_line` — 70 columns

Same grain as the fact. Every column and its type is declared in
`wide_world_importers_dw/models/marts/sales/schema.yml` under `contract: enforced`, which is the
authoritative list — an upstream column that would change it fails the build rather than arriving
here silently. It is not repeated in this file, because two copies of a 70-column list is how a
catalog starts lying.

Shape, in order: 9 fact measures and degenerate dimensions, 28 `customer_*` attributes,
`bill_to_customer_name`, 3 person names in their roles, 4 stock item attributes, 1 package type,
then 24 date attributes — the full calendar for the order date and the expected delivery date,
and `full_date` alone for the two picking-completed dates.

**No foreign key reaches the mart.** The attribute is already here, so a consumer never joins back.

## Counts

**Row counts are deliberately absent from this file.** They change the moment the data span
changes — extending the source forward is planned work — and a count copied into prose becomes a
second source of truth that nobody remembers to update. Column counts stay, because those move only
when someone edits a model, and the mart's are held by an enforced contract.

For current numbers:

```bash
make shape
```

`data/snapshots/manifest.json` is authoritative for **source** row counts, and
`assert_staging_matches_manifest` fails the build if the warehouse disagrees with it. So the
numbers are asserted, not just available.
