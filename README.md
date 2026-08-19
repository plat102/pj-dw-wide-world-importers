# Wide World Importers Data Warehouse
> A data warehouse project built from the **Wide World Importers** operational database, designed to consolidate business data into a dimensional model optimized for analytics and visualization.

[![dbt](https://img.shields.io/badge/dbt-FF694B?logo=dbt&logoColor=white)](https://www.getdbt.com/)
[![DuckDB](https://img.shields.io/badge/DuckDB-FFF000?logo=duckdb&logoColor=black)](https://duckdb.org/)
[![Parquet](https://img.shields.io/badge/Apache%20Parquet-50ABF1?logo=apacheparquet&logoColor=white)](https://parquet.apache.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![SQL Server](https://img.shields.io/badge/SQL%20Server-CC2927?logo=microsoft-sql-server&logoColor=white)](https://www.microsoft.com/sql-server)
[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)](https://www.python.org/)

---

## 📊 Overview

A **DuckLake lakehouse** built from the Wide World Importers OLTP database: dlt extracts a frozen
Parquet snapshot from SQL Server, the snapshot is published to an S3-compatible object store, and
dbt builds a Kimball star schema over it. The warehouse is Parquet on the store with its catalog in
Postgres — not a file in this directory.

| Layer | Technology | Description |
|--------|-------------|-------------|
| **Source** | SQL Server | Wide World Importers OLTP, read through one read-only login |
| **Extraction** | dlt | 21 tables to Parquet inside one snapshot-isolation transaction |
| **Storage** | S3-compatible object store | The snapshot under `bronze/<snapshot-id>/`, the lake under `lake/` |
| **Warehouse** | DuckLake (DuckDB + Postgres catalog) | raw → staging → analytics → mart |
| **Transformation** | dbt Core | Modular ELT, dimensional modeling, an enforced contract on the mart |

**Business Problem:** Analytical queries slow down the transactional system; business teams rely on
IT for ad-hoc reports.
**Solution:** A dimensional warehouse with star schema models, reproducible from a checksummed
snapshot.
**Outcomes:** Faster insights, self-service reporting, and a build that can be proven identical
twice over.

![Data Warehouse ERD](docs/image/dwh_erd.png)
*Figure: Dimensional model overview*

---

## 🏗️ Architecture

Two stages, and the boundary between them is the point: **the extraction holds the source
credential and nothing downstream can reach the source.** That is enforced, not just described —
`make lint` fails the build if any package outside the source connector acquires the means to
connect.

```mermaid
flowchart LR
    subgraph source["📦 Source"]
        OLTP[Wide World Importers<br/>SQL Server]
    end

    subgraph ingest["⚡ Extraction"]
        direction TB
        DLT[dlt<br/>one snapshot-isolation<br/>transaction]
        MANIFEST[manifest.json<br/>checksums, row counts, types]
    end

    subgraph store["🪣 Object store"]
        BRONZE[bronze/&lt;snapshot-id&gt;/<br/>Parquet]
    end

    subgraph dwh["🦆 DuckLake<br>lakehouse"]
        direction TB
        STG[Staging<br/>main_stg]
        ANALYTICS[Analytics<br/>main_dwh]
        MART[Mart<br/>main_mart]

        STG -->|dbt| ANALYTICS
        ANALYTICS -->|dbt| MART
    end

    subgraph bi["📊 Visualization"]
        LOOKER[Looker Studio<br/>frozen exhibit]
    end

    OLTP --> DLT
    DLT --> MANIFEST
    DLT --> BRONZE
    BRONZE -->|dbt reads s3://| STG
    MART -.-> LOOKER

    style OLTP fill:#E8E8E8,stroke:#666,stroke-width:2px,color:#333
    style DLT fill:#FFE4B5,stroke:#FFA500,stroke-width:2px,color:#333
    style MANIFEST fill:#FFE4B5,stroke:#FFA500,stroke-width:2px,color:#333
    style BRONZE fill:#FFF9C4,stroke:#FBC02D,stroke-width:2px,color:#333
    style STG fill:#E3F2FD,stroke:#2196F3,stroke-width:2px,color:#333
    style ANALYTICS fill:#E3F2FD,stroke:#2196F3,stroke-width:2px,color:#333
    style MART fill:#E3F2FD,stroke:#2196F3,stroke-width:2px,color:#333
    style LOOKER fill:#EEEEEE,stroke:#9E9E9E,stroke-width:2px,stroke-dasharray: 5 5,color:#333
```

**Data Layers** — one lakehouse catalog, the layers are schemas inside it.

- `bronze/<snapshot-id>/` — the Parquet snapshot on the object store, read in place
- `main_stg` — staging (`stg_`) and intermediate (`int_`)
- `main_dwh` — dimensional models (`dim_`, `fact_`)
- `main_mart` — denormalized reporting datasets (`mart_`)

---

## 📂 Project Structure

```
├── docs/                           # Project documentation
├── infrastructure/                 # Container config and the source login SQL
├── data/
│   ├── demo/                       # Committed fixture: real rows, ~2.4 MB
│   └── snapshots/manifest.json     # The snapshot contract (the Parquet is not committed)
├── src/
│   ├── cli/                        # The `wwi` command
│   ├── config/                     # Settings; the only place an env var is named
│   ├── connectors/                 # mssql, s3, ducklake
│   ├── contracts/                  # Manifest, paths, types, dbt sources projection
│   ├── ingestion/                  # Source → Parquet → object store
│   ├── warehouse/                  # Reading the built warehouse
│   ├── demo/                       # The fresh-clone path
│   └── utils/
├── tests/                          # unit/ needs nothing; integration/ needs the stack
├── wide_world_importers_dw/        # dbt project
│   ├── models/
│   │   ├── staging/                # Source data standardization
│   │   ├── analytics/              # Dimensional models (dim_*, fact_*)
│   │   └── marts/                  # Denormalized reporting datasets
│   └── dbt_project.yml
└── docker-compose.yml              # Object store + DuckLake catalog
```

## 📈 Sample Reports — a frozen exhibit

**These dashboards run against a BigQuery build that is no longer maintained.** The warehouse moved
to DuckLake; the BigQuery datasets (`wwi_raw` / `wwi_stg` / `wwi_dwh` / `wwi_mart`) and the ingestion
that fed them are kept as an exhibit of what the project looked like, not as something you can
reproduce from this repository. Nothing here builds them.

[View Live Dashboard](https://lookerstudio.google.com/reporting/54a88f82-aeee-494c-b81f-31bb320f299c)

![Looker Studio Example](docs/image/looker_studio.png)

## 📚 Documentation

- [Project Roadmap](docs/project_roadmap.md) - Business context, objectives, status, and future plans
- [Technical Design](docs/technical_design.md) - Architecture and technology stack
- [Data Modeling](docs/data_modelling.md) - Dimensional model design
- [Data Catalog](docs/data_warehouse_catalog.md) - Table and column definitions
- [Naming Conventions](docs/naming_convention.md) - Standards and best practices

## 🚀 Quick Start

**Requirements:** `git`, `make`, [uv](https://docs.astral.sh/uv/) and a container runtime. That is
the whole list -- no cloud account, no SQL Server, and nothing to fill in by hand.

```bash
make demo
```

One command, and it does not shorten anything away: it installs the pinned environment and the dbt
packages, writes a `.env` with generated local credentials, brings up the object store and the
DuckLake catalog, publishes the committed fixture, **verifies every object against its checksum**,
builds all 23 models, runs all 44 tests, and prints every relation with its row count. Measured on a
fresh clone with no source database: **36 seconds cold, 31 seconds on a second run.**

It refuses rather than guesses in two places. If `MSSQL_CONNECTION_STRING` is set it stops -- the
transform half must never be able to reach the source. If the lake already holds a warehouse this
fixture did not build, it stops and names the row counts that told it so, rather than mixing fixture
rows into a real warehouse.

<details>
<summary>The same thing as separate steps</summary>

```bash
make install                # the pinned environment
make deps                   # the dbt packages -- dbt_packages/ is git-ignored, so this is not optional
cp .env.example .env        # then set the store and catalog credentials
cp profiles.sample.yml ~/.dbt/profiles.yml
make up                     # object store, DuckLake catalog, bucket
make seed_bronze_empty      # or `make seed_bronze` with a real snapshot in data/raw/
make build
```

</details>

**The Parquet snapshot is not in this repository and never will be** -- only the manifest that
describes it is. What a fresh clone does have is `data/demo/`: a reduced, labelled derivative of
that snapshot, ~2.4 MB, carrying every dimension whole and one window of facts. It has its own
manifest with its own real checksums, so a clone runs the same seed-and-verify path the shipped
snapshot does and the warehouse it builds returns numbers rather than empty relations.

Two artifacts, one contract. The snapshot is what the extraction produces and what the warehouse is
built from in earnest; the fixture is what makes the repository runnable by someone who has neither
SQL Server nor 24 MB of Parquet. Nothing downstream can tell them apart -- no model, test or macro
names either one, and `SNAPSHOT_ID` is the only thing that selects between them.

With the real snapshot in `data/raw/`, `make seed_bronze` publishes it to the store instead and the
build produces the warehouse in full: 23 models and 44 tests.

`make seed_bronze_empty` remains for the third case, and it is worth knowing what it is for: it
writes zero-row Parquet carrying the manifest's exact columns and types, so every model still
executes and a renamed or missing column fails on a binder error, while anything data-dependent
passes trivially on no rows. It answers "did a column break", not "is the data right".

The warehouse is a DuckLake lakehouse -- Parquet on the object store, catalog in Postgres -- not a
file in this directory. `make shape` prints every relation with its row and column count, read
through a fresh connection that attaches nothing but the catalog and the store.

Worth knowing:

```bash
make verify     # check the published snapshot against its manifest
make shape      # every relation with its row and column count
make down       # stop the stack, keeping the data (clean_storage deletes it)
make extract    # refresh the snapshot from SQL Server; one read-only login, no sa
```
