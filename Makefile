run_etl:
	python etl/dbt_mssql_to_bigquery.py

run_dbt:
    dbt run --project-dir ./wide_world_importers_dw --profiles-dir ./wide_world_importers_dw

dlt_pl_list:
	dlt pipeline --list-pipelines

run_dlt:
	dlt pipeline mssql_to_bigquery sync

full_pipeline: run_etl run_dbt
