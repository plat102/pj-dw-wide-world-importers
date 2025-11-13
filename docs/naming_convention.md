# Naming Conventions

Naming standards and code style guidelines for consistency across the project

## dbt Models

> File naming and folder organization standards for dbt models

### File Naming

| Layer                 | Prefix    | Materialization | Example                       |
| --------------------- | --------- | --------------- | ----------------------------- |
| Staging               | `stg_`  | View            | `stg_sales_customer.sql`    |
| Intermediate          | `int_`  | View            | `int_customer_enriched.sql` |
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
├── analytics/
│   ├── dim_*.sql               # Dimension tables
│   ├── fact_*.sql              # Fact tables
│   └── role_playing_dimension/ # Views on dimension tables
└── marts/
    └── sales/                  # Grouped by business domain
```

## Database Objects

Naming conventions for tables and columns in BigQuery

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
| General            | snake_case                 | `customer_name`, `unit_price`                  |

### Datasets (BigQuery)

| Dataset      | Purpose                              |
| ------------ | ------------------------------------ |
| `wwi_raw`  | Raw source data, unmodified          |
| `wwi_stg`  | Staging and intermediate models      |
| `wwi_dwh`  | Production dimensional models        |
| `wwi_mart` | Business-ready denormalized datasets |

## SQL Style Guide

> SQL formatting standards for readability and maintainability

This project follows **dbt's SQL style guide** with lowercase keywords and trailing commas.

### Keywords & Formatting

- **Lowercase** for SQL keywords: `select`, `from`, `where`, `join`, `as`
- **Trailing commas**: Place comma at the end of each line (except last)
- **One column per line** in SELECT statements
- **Indentation**: 4 spaces for nested blocks

```sql
select
    customer_key,
    customer_name,
    credit_limit
from dim_customer
```

### Joins

- Align `on` with table name
- Use explicit join types (`left join`, `inner join`)

```sql
select
    c.customer_name,
    o.order_date
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
        customer_key,
        count(*) as order_count
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

### Testing

- Add generic tests in `schema.yml` files
- Test primary keys for uniqueness and not-null
- Test foreign key relationships
