# Data Transformation Pipeline

Describe how dbt orchestrates ELT transformations.

## Pipeline Flow
- dbt DAG overview (staging → core → mart)
- Execution order and dependencies

![Pipeline Flow]()

## Commands and Jobs
Example CLI commands:
```bash
dbt run --select +fact_sales_order_line
dbt test
dbt docs generate
```
