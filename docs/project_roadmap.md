# Project Roadmap

Business context, objectives, current status, and future direction of the data warehouse project

**Project Type**: Learning Project `<br>`
**Current Phase**: Phase 1 Complete (Sales Order) `<br>`
**Next Milestone**: Automated ingestion + Purchase Order analytics

---

## 📊 Business Context

Wide World Importers relies on an OLTP database optimized for transactions, creating analytical challenges:

- **Performance bottleneck**: Analytical queries slow down operational systems
- **Complex data access**: Business insights require joining 10+ normalized tables
- **No historical tracking**: Cannot analyze trends or changes over time
- **IT dependency**: Business users wait days for custom reports

**Business Impact:** Delayed decision-making, missed sales opportunities, inability to forecast accurately

---

## 🎯 Objective

Build a modern cloud-based data warehouse to enable self-service analytics and data-driven decision making.

**Primary Goals:**

1. Implement a dimensional model optimized for sales analytics
2. Establish a scalable ELT pipeline using modern data stack
3. Enable business users to create their own reports via BI tools
4. Demonstrate best practices in data warehouse design and implementation

**Target Users:**

- Sales managers analyzing performance by customer, product, and time period
- Operations team monitoring order fulfillment and delivery metrics
- Executives tracking KPIs and business trends

## ☑️Success Criteria

### Functional Requirements

- ✅ **Data Completeness**: All sales transaction data from source system available in warehouse
- ✅ **Performance**: Dashboard queries execute in < 5 seconds
- ✅ **Flexibility**: Business users can slice and dice data without SQL knowledge
- ✅ **Accuracy**: Data reconciliation between source and warehouse shows 100% match

### Technical Requirements

- ✅ **Scalability**: Architecture supports additional business processes (purchases, inventory)
- ✅ **Maintainability**: Version-controlled transformations with clear documentation
- ✅ **Cost Efficiency**: Cloud-based solution with minimal operational overhead
- 🚧 **Data Quality**: Automated testing and validation (in progress)
- 🚧 **Automation**: Scheduled incremental loads (planned)

## 📋 Project Scope

### In Scope

- **Business Process**: Sales Order (order processing, fulfillment, delivery)
- **Data Sources**: Wide World Importers OLTP database
- **Deliverables**:
  - Dimensional data warehouse (star schema)
  - BI dashboards for sales performance analysis
  - Complete technical documentation
  - Historical change tracking (SCD Type 2)
- **Technology**: Cloud-based modern data stack (BigQuery, dbt, Looker Studio)

### Out of Scope

- Real-time data ingestion
- Advanced data science/ML capabilities
- Production-grade orchestration and monitoring

## 🚀 Current Status & Known Limitations

**Phase 1: Sales Analytics** Complete

### What's Working

- ✅ Sales analytics capability
- ✅ Sub-5-second dashboard queries
- ✅ 100% data accuracy (validated against source)
- ✅ Business users creating their own Looker Studio reports

### Current Limitations

- ⚠️ **Manual data loading**: CSV export/import (automation in progress)
- ⚠️ **Single business process**: Sales only (purchases planned Q2)
- ⚠️ **No change tracking**: Type 0 dimensions (overwrite on change)
- ⚠️ **Limited testing**: Basic validation only (comprehensive tests planned)

### Technical Debt

- Refactor staging layer for consistency
- Implement data quality framework (Great Expectations or dbt tests)
- Add incremental strategies to large fact tables
- Document troubleshooting procedures

## 🗺️ Future Roadmap

### Phase 2: Infrastructure Automation (Near)

- **Automated ingestion**: Complete dlt pipeline for incremental loads from SQL Server
- **Data quality**: Implement dbt testing framework (uniqueness, not-null, referential integrity)
- **Incremental strategies**: Optimize dbt models for performance

### Phase 3: Business Expansion (Medium)

- **Purchase Order analytics**: Procurement metrics and supplier performance
- **Inventory management**: Stock movements, turnover, and valuation
- **Orchestration**: Airflow/Prefect for scheduled runs and dependency management
- **Performance optimization**: BigQuery partitioning, clustering, query tuning

### Phase 4: Advanced Capabilities (Long)

- **Customer intelligence**: Lifetime value, segmentation, churn prediction
- **Historical tracking**: SCD Type 2 for dimension changes over time
- **Data governance**: Cataloging, access controls, retention policies
- **Advanced visualization**: Interactive dashboards with drill-down capabilities
- **Documentation automation**: dbt docs site with lineage visualization

### Risks & Mitigation

| Risk                             | Impact              | Mitigation                                      |
| -------------------------------- | ------------------- | ----------------------------------------------- |
| **Source system changes**  | Breaking pipeline   | Version control, schema validation              |
| **BigQuery cost overruns** | Budget exceeded     | Query optimization, partitioning                |
| **Data quality issues**    | Incorrect analytics | Automated testing framework                     |
| **Scope creep**            | Delayed delivery    | Strict phase boundaries, backlog prioritization |

## 🔌 Extension Path

The architecture is designed for extensibility. Adding new business processes follows a repeatable pattern.

### Future Business Processes

The architecture is designed to support additional business processes with minimal rework. Each new process follows the same pattern: **source → staging → analytics → marts**

**Potential Extensions:**

- **Purchase Order analytics**: Procurement metrics, supplier performance
- **Inventory management**: Stock movements, turnover, valuation
- **Customer intelligence**: Lifetime value, segmentation, churn prediction

**New Dimensions (as needed):**

- Dim tables for procurement analytics
- Dim tables for inventory location analysis
- Additional conformed dimensions shared across business processes

---
