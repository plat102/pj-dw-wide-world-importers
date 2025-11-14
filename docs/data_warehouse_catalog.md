# Data Warehouse Catalog

**Purpose**: Data dictionary - comprehensive reference for all datasets, tables, and columns in the warehouse

## Datasets

**Purpose**: Overview of BigQuery datasets and their access patterns

| Dataset      | Schema    | Purpose                                | Access Level               |
| ------------ | --------- | -------------------------------------- | -------------------------- |
| `wwi_raw`  | Raw       | Unmodified source data from SQL Server | ETL processes only         |
| `wwi_stg`  | Staging   | Cleansed, standardized source data     | Internal transformations   |
| `wwi_dwh`  | Analytics | Production dimensional models          | BI tools, analysts         |
| `wwi_mart` | Marts     | Denormalized reporting datasets        | Business users, dashboards |

## Dimensional Model

**Purpose**: Detailed schema definitions for all fact and dimension tables

### Fact Tables

#### `fact_sales_order_line`

**Purpose**: Sales transactions at order line item level
**Grain**: One row per order line
**Source**: `sales.Orders` + `sales.OrderLines` (SQL Server)

| Column                                          | Type    | Description               | Source                   |
| ----------------------------------------------- | ------- | ------------------------- | ------------------------ |
| `sales_order_line_key`                        | INTEGER | Primary key               | OrderLineID              |
| `sales_order_key`                             | INTEGER | Order identifier          | OrderID                  |
| `customer_key`                                | INTEGER | FK to dim_customer        | CustomerID               |
| `stock_item_key`                              | INTEGER | FK to dim_stock_item      | StockItemID              |
| `package_type_key`                            | INTEGER | FK to dim_package_type    | PackageTypeID            |
| `salesperson_key`                             | INTEGER | FK to dim_person          | SalespersonPersonID      |
| `contact_person_key`                          | INTEGER | FK to dim_person          | ContactPersonID          |
| `picked_by_person_key`                        | INTEGER | FK to dim_person          | PickedByPersonID         |
| `order_date_key`                              | STRING  | FK to dim_date (YYYYMMDD) | OrderDate                |
| `expected_delivery_date_key`                  | STRING  | FK to dim_date            | ExpectedDeliveryDate     |
| `sales_order_line_picking_completed_date_key` | STRING  | FK to dim_date            | PickingCompletedWhen     |
| `quantity`                                    | INTEGER | Quantity ordered          | Quantity                 |
| `unit_price`                                  | NUMERIC | Price per unit            | UnitPrice                |
| `tax_rate`                                    | NUMERIC | Tax percentage            | TaxRate                  |
| `picked_quantity`                             | INTEGER | Quantity picked           | PickedQuantity           |
| `is_undersupply_backordered`                  | BOOLEAN | Backorder flag            | IsUndersupplyBackordered |

### Dimension Tables

> Reference data for analysis - customers, products, people, dates, etc.

#### `dim_customer`

**Purpose**: Customer master data
**Grain**: One row per customer
**Type**: Type 0 (no historical tracking)

| Column                        | Type    | Key Attributes        |
| ----------------------------- | ------- | --------------------- |
| `customer_key`              | INTEGER | Primary key           |
| `customer_name`             | STRING  | Business name         |
| `customer_category_name`    | STRING  | Customer segment      |
| `buying_group_name`         | STRING  | Purchasing consortium |
| `credit_limit`              | NUMERIC | Credit limit amount   |
| `payment_term_days`         | INTEGER | Payment terms         |
| `is_on_credit_hold`         | BOOLEAN | Credit status         |
| `delivery_city_name`        | STRING  | Delivery location     |
| `delivery_country_name`     | STRING  | Delivery country      |
| `primary_contact_full_name` | STRING  | Main contact person   |

#### `dim_stock_item`

**Purpose**: Product catalog
**Grain**: One row per stock item
**Type**: Type 0

| Column                       | Type    | Description            |
| ---------------------------- | ------- | ---------------------- |
| `stock_item_key`           | INTEGER | Primary key            |
| `stock_item_name`          | STRING  | Product name           |
| `supplier_name`            | STRING  | Supplier               |
| `color_name`               | STRING  | Product color          |
| `brand`                    | STRING  | Brand name             |
| `size`                     | STRING  | Product size           |
| `unit_price`               | NUMERIC | Selling price          |
| `recommended_retail_price` | NUMERIC | RRP                    |
| `is_chiller_stock`         | BOOLEAN | Requires refrigeration |
| `lead_time_days`           | INTEGER | Procurement lead time  |

#### `dim_person`

**Purpose**: People (employees, contacts) - Role-playing dimension
**Grain**: One row per person
**Type**: Type 0

| Column               | Type    | Description      |
| -------------------- | ------- | ---------------- |
| `person_key`       | INTEGER | Primary key      |
| `person_full_name` | STRING  | Full name        |
| `email_address`    | STRING  | Email            |
| `phone_number`     | STRING  | Phone            |
| `is_employee`      | BOOLEAN | Employee flag    |
| `is_salesperson`   | BOOLEAN | Salesperson flag |
| `is_system_user`   | BOOLEAN | System user flag |

**Usage**: Referenced by fact table for salesperson, contact person, and picker roles

#### `dim_package_type`

**Purpose**: Package type lookup
**Grain**: One row per package type

| Column                | Type    | Description         |
| --------------------- | ------- | ------------------- |
| `package_type_key`  | INTEGER | Primary key         |
| `package_type_name` | STRING  | Package description |

#### `dim_date`

**Purpose**: Calendar dimension for time intelligence
**Grain**: One row per day (2000-01-01 to 2050-12-31)
**Type**: Static, pre-generated

| Column             | Type    | Description                        |
| ------------------ | ------- | ---------------------------------- |
| `date_key`       | STRING  | Primary key (YYYYMMDD format)      |
| `full_date`      | DATE    | Calendar date                      |
| `year`           | INTEGER | Calendar year                      |
| `year_week`      | INTEGER | Year + ISO week (YYYYWW)           |
| `fiscal_year`    | INTEGER | Fiscal year (Apr-Mar)              |
| `fiscal_qtr`     | STRING  | Fiscal quarter (Q1-Q4)             |
| `month`          | INTEGER | Month number (1-12)                |
| `month_name`     | STRING  | Month name (January, etc.)         |
| `week_day`       | INTEGER | Day of week (1=Sunday, 7=Saturday) |
| `day_name`       | STRING  | Day name (Monday, etc.)            |
| `day_is_weekday` | BOOLEAN | Weekday indicator (Mon-Fri = 1)    |

## Mart Tables

> Pre-joined datasets optimized for BI tools (eliminates join complexity for end users)

#### `mart_sales_order_line`

**Purpose**: Fully denormalized sales dataset for BI consumption
**Grain**: One row per order line with all dimension attributes joined

**Structure**: Fact measures + all columns from related dimensions with prefixes:

- `customer_*` - Customer attributes
- `salesperson_*` - Salesperson attributes
- `order_date_*` - Order date attributes
- etc.

**Generation**: Built using dbt macros (`get_filtered_columns_in_relation`) to automatically select and prefix columns
