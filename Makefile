run_etl:
	python etl/dbt_mssql_to_bigquery.py

run_dbt:
	dbt run --profiles-dir ./dbt

full_pipeline: run_etl run_dbt
