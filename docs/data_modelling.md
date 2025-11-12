# Dimensional Modelling

This document describes the dimensional modelling process for the **Wide World Importers Data Warehouse**.  
It covers business requirements, conceptual design, and detailed implementation steps.

---

## 1. Requirement Gathering

### 1.1 Source System Profile
Describe all source systems feeding the warehouse, including:
- System names (e.g., CRM, ERP)
- Main entities (customers, products, sales, etc.)
- Data refresh frequency
- Connectivity method (ODBC, API, file ingestion)

### 1.2 User Stories & KPI Description
Document business requirements as user stories and key metrics to be supported by the warehouse, e.g.:
- *“As a sales manager, I want to track monthly revenue by product category.”*
- *“As a logistics analyst, I want to measure average delivery time.”*

---

## 2. High-level Design

### 2.1 Business Processes
List core business processes to be modeled as fact tables (e.g., *Sales Orders*, *Purchasing*, *Inventory Movement*).  
Each process should align with a key business KPI.

### 2.2 Bus Matrix
Provide a bus matrix mapping business processes to dimensions.  
(Example: rows = fact tables, columns = shared dimensions.)

### 2.3 ERD
The following diagram illustrates the high-level star schema for the Data Warehouse:

![Data Warehouse ERD](./image/dwh_erd.png)

---

## 3. Detailed Design & Implementation

### 3.1 Source-to-Target Mapping
Define how source system fields map to data warehouse tables and columns.  
Include transformations, business rules, and surrogate key generation logic.

### 3.2 Dimension Tables Description
Summarize each dimension, including:
- Business meaning
- Grain
- Surrogate key
- SCD type (Type 1, 2, etc.)
- Data quality notes

👉 [View in data catalog](./data_catalog/dim_tables.md)

### 3.3 Fact Tables Description
Detail each fact table:
- Business process represented
- Grain of the fact
- Additive / semi-additive measures
- Foreign key references to dimensions

👉 [View in data catalog](./data_catalog/fact_tables.md)

---