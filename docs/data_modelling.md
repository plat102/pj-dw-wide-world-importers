# Data Modeling

Document the dimensional model design - business requirements, star schema, and table general specifications.

## Business Requirements

> Define business objectives and metrics that drive the dimensional model design

### Objective

Build a dimensional data warehouse to support analytics for Wide World Importers.

**Current Implementation**: Sales Order analytics
**Future Scope**: Purchase Orders, Inventory Management, Customer Intelligence

### Key Metrics

#### Sales Order Process

- **Revenue**: Total sales amount by order line
- **Quantity**: Units sold and picked
- **Fulfillment**: Order-to-delivery cycle time
- **Customer**: Retention, lifetime value, geographic distribution

## Dimensional Model Design

**Purpose**: Define the star schema structure - bus matrix, fact/dimension tables, and their relationships

### Business Process Scope

**Implemented**: Sales Order Line (transactional sales data)

**Planned for Future Implementation**:

- Purchase Order Line (procurement analytics)
- Inventory Transaction (stock movements)
- Stock Holding (inventory snapshots)

### Star Schema

![Star Schema ERD](image/dwh_erd.png)

### Bus Matrix

**Current Implementation**:

| Business Process | Customer | Stock Item | Person            | Package Type | Date |
| ---------------- | -------- | ---------- | ----------------- | ------------ | ---- |
| Sales Order Line | ✓       | ✓         | ✓ (role-playing) | ✓           | ✓   |

**Future Business Processes** may introduce additional dimensions (Supplier, Warehouse Location, etc.)

### Tables Overview

**Fact Table:**

- `fact_sales_order_line` - Transactional sales data at order line grain

**Dimension Tables:**

- `dim_customer` - Customer master with geographic and category attributes
- `dim_stock_item` - Product catalog with supplier and color details
- `dim_person` - People (employees and contacts)
- `dim_package_type` - Package type lookup
- `dim_date` - Calendar dimension with fiscal attributes

**Role-Playing Dimensions:**

- `dim_person` reused for salesperson, contact person, picked by person
- `dim_date` reused for order date, expected delivery date, picking completed dates

## Implementation

> Detailed specifications for fact and dimension tables - grain, keys, attributes

### Fact Table: `fact_sales_order_line`

**Grain**: One row per order line item

**Measures:**

- `quantity` - Units ordered
- `unit_price` - Price per unit
- `tax_rate` - Tax percentage
- `picked_quantity` - Units picked

### Dimension Tables

| Dimension                  | Grain                    | Type                 | Key Attributes                                                                                   | Notes                                                 |
| -------------------------- | ------------------------ | -------------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| **dim_customer**     | One row per customer     | Type 0 (static)      | Customer name, category, buying group, contact details, delivery/postal addresses, payment terms | -                                                     |
| **dim_stock_item**   | One row per stock item   | Type 0 (static)      | Product name, supplier, color, chiller stock indicator                                           | -                                                     |
| **dim_person**       | One row per person       | Type 0 (static)      | Full name, email, phone, employee/salesperson flags                                              | Role-playing dimension (salesperson, contact, picker) |
| **dim_package_type** | One row per package type | Type 0 (static)      | Package type name                                                                                | -                                                     |
| **dim_date**         | One row per calendar day | Static pre-populated | Date components (year, month, day), day of week, ISO week, month name                            | -                                                     |

## Marts Layer

> Pre-joined, denormalized datasets optimized for BI consumption.

### `mart_sales_order_line`

Fully denormalized fact with all dimension attributes joined, eliminating need for BI tool to perform joins. Generated using dbt macros to dynamically select columns from each dimension.

## Data Lineage

> Map source tables to staging models to final dimensional models (transformation flow).

*Note: This shows logical data transformation dependencies. For physical infrastructure flow, see technical_design.md*

```
Source (SQL Server)             Staging (Views)                 Analytics (Tables)
─────────────────────           ───────────────────             ──────────────────
sales.Orders            ──>     stg_sales_order          ──┐
sales.OrderLines        ──>     stg_sales_order_line     ──┼──> fact_sales_order_line
                                                           │
sales.Customers         ──>     stg_sales_customer       ──┴──> dim_customer
warehouse.StockItems    ──>     stg_warehouse_stock_item   ───> dim_stock_item
application.People      ──>     stg_application_person     ───> dim_person
warehouse.PackageTypes  ──>    stg_warehouse_package_type    ─> dim_package_type
(Generated)                                                ───> dim_date
```

