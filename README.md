# pj-dw-wide-world-importers


### **BigQuery Structure**

**1. Project**

* `thupla-dw-dev`:  the development environment

**2. Datasets**

* **`wwi_raw`** : ✅ Stores raw data as ingested directly from the source
* **`wwi_stg`** : ✅ For staging and intermediate models.
  * Cleaned/standardized data tables.
  * Join and transform raw tables for analytics preparation.
* **`wwi_dwh`** : ✅ For finalized models (e.g., facts and dimensions)

### dbt models

dbt project /models:

```
/staging
---/wide_world_importers
stg_X.sql
/analytics
dim_X.sql
fact_X.sql
---/marts
    mart_
/intermediate
int_X.sql
/exposures
```
