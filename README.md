# Wide World Importers Data Warehouse
> A data warehouse project built from the **Wide World Importers** operational database, designed to consolidate business data into a dimensional model optimized for analytics and visualization.

[![dbt](https://img.shields.io/badge/dbt-FF694B?logo=dbt&logoColor=white)](https://www.getdbt.com/)
[![BigQuery](https://img.shields.io/badge/BigQuery-669DF6?logo=google-cloud&logoColor=white)](https://cloud.google.com/bigquery)
[![SQL Server](https://img.shields.io/badge/SQL%20Server-CC2927?logo=microsoft-sql-server&logoColor=white)](https://www.microsoft.com/sql-server)
[![Looker Studio](https://img.shields.io/badge/Looker%20Studio-4285F4?logo=looker&logoColor=white)](https://lookerstudio.google.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)](https://www.python.org/)

---

## 📊 Overview

This project consolidates **Wide World Importers** OLTP data into a **BigQuery** data warehouse using **dbt** for transformation and **Looker Studio** for visualization.

| Layer | Technology | Description |
|--------|-------------|-------------|
| **Source** | SQL Server | Wide World Importers OLTP database |
| **Ingestion** | Manual upload | Data ingestion pipeline to BigQuery. Plan to dlt |
| **Warehouse** | BigQuery | Cloud data warehouse (raw → staging → DWH → mart) |
| **Transformation** | dbt Core | Modular ELT transformations, dimensional modeling |
| **Visualization** | Looker Studio | Interactive dashboards & self-service BI |

**Business Problem:** Analytical queries slow down the transactional system; business teams rely on IT for ad-hoc reports.  
**Solution:** A scalable cloud data warehouse with star schema models and self-service BI.  
**Outcomes:** Faster insights, sub-5s dashboards, and reduced IT dependency.

![Data Warehouse ERD](docs/image/dwh_erd.png)
*Figure: Dimensional model overview*

---

## 🏗️ Architecture

**Data Flow**

```mermaid
flowchart LR
    subgraph source["📦 Source"]
        OLTP[Wide World Importers<br/>OLTP Database]
    end
    
    subgraph ingest["⚡ Ingestion"]
        direction TB
        CSV[<b>Manual Upload<br/>CSV</b>]
        DLT["(dlt Pipeline)"]
    end
    
    subgraph dwh["☁️ BigQuery<br>Data Warehouse"]
        direction TB
        
        RAW[Raw Layer<br/>wwi_raw]
        STG[Staging<br/>wwi_stg]
        ANALYTICS[Analytics<br/>wwi_dwh]
        MART[Mart<br/>wwi_mart]
        
        RAW -->|dbt| STG
        STG -->|dbt| ANALYTICS
        ANALYTICS -->|dbt| MART
    end
    
    subgraph bi["📊 Visualization"]
        LOOKER[Looker Studio<br/>Dashboards]
    end
    
    OLTP --> CSV
    OLTP -.-> DLT
    CSV --> RAW
    DLT -.-> RAW
    MART ==> LOOKER
    
    style OLTP fill:#E8E8E8,stroke:#666,stroke-width:2px,color:#333
    style CSV fill:#FFE4B5,stroke:#FFA500,stroke-width:2px,color:#333
    style DLT fill:#FFE4B5,stroke:#FFA500,stroke-width:2px,stroke-dasharray: 5 5,color:#333
    style RAW fill:#E3F2FD,stroke:#2196F3,stroke-width:2px,color:#333
    style STG fill:#E3F2FD,stroke:#2196F3,stroke-width:2px,color:#333
    style ANALYTICS fill:#E3F2FD,stroke:#2196F3,stroke-width:2px,color:#333
    style MART fill:#E3F2FD,stroke:#2196F3,stroke-width:2px,color:#333
    style LOOKER fill:#C8E6C9,stroke:#4CAF50,stroke-width:2px,color:#333
```

**Data Layers**

- `wwi_raw` - Raw data ingested from source
- `wwi_stg` - Staging and intermediate transformations
- `wwi_dwh` - Dimensional models (facts & dimensions)
- `wwi_mart` - Denormalized reporting datasets


---

## 📂 Project Structure

```
├── docs/                           # Project documentation
├── etl/                            # Data ingestion scripts
├── wide_world_importers_dw/        # dbt project
│   ├── models/
│   │   ├── staging/                # Source data standardization
│   │   ├── analytics/              # Dimensional models (dim_*, fact_*)
│   │   └── marts/                  # Denormalized reporting datasets
│   └── dbt_project.yml
└── scripts/                        # Utility SQL scripts
```

## 📈 Sample Reports

[View Live Dashboard](https://lookerstudio.google.com/reporting/54a88f82-aeee-494c-b81f-31bb320f299c)

![Looker Studio Example](docs/image/looker_studio.png)

## 📚 Documentation

- [Project Roadmap](docs/project_roadmap.md) - Business context, objectives, status, and future plans
- [Technical Design](docs/technical_design.md) - Architecture and technology stack
- [Data Modeling](docs/data_modelling.md) - Dimensional model design
- [Data Catalog](docs/data_warehouse_catalog.md) - Table and column definitions
- [Naming Conventions](docs/naming_convention.md) - Standards and best practices

## 🚀 Quick Start

**Requirements:** Python 3.11+ and [uv](https://docs.astral.sh/uv/). No cloud account, and no SQL
Server unless you want to refresh the snapshot.

```bash
# Install the pinned environment
make install

# Point dbt at a profile (the duckdb target is the default)
cp profiles.sample.yml ~/.dbt/profiles.yml

# Check the Parquet snapshot against its manifest, then build
make verify
make build
```

`make build` writes `wwi.duckdb` in the repository root and runs 26 models and 50 tests. Query it
with `duckdb wwi.duckdb`, or run `make shape` to see every relation with its row and column count.

Two more worth knowing:

```bash
make shape      # every relation with its row and column count
make compare    # build twice, diff every relation -- proves the build is deterministic
make extract    # refresh the snapshot from SQL Server; needs the source and sa
```
