# Recipes must be indented with a TAB. Spaces make GNU make fail to parse the file.
# `uv run` resolves the environment from uv.lock; no venv activation needed.
DBT_DIR := wide_world_importers_dw
PROFILES_ARG := $(if $(PROFILES_DIR),--profiles-dir $(PROFILES_DIR),)
DBT := uv run dbt

.PHONY: install deps parse run_dbt test_dbt build run_etl dlt_pl_list run_dlt full_pipeline

install:
	uv sync --frozen

deps:
	$(DBT) deps --project-dir ./$(DBT_DIR) $(PROFILES_ARG)

parse:
	$(DBT) parse --project-dir ./$(DBT_DIR) $(PROFILES_ARG)

run_dbt:
	$(DBT) run --project-dir ./$(DBT_DIR) $(PROFILES_ARG)

test_dbt:
	$(DBT) test --project-dir ./$(DBT_DIR) $(PROFILES_ARG)

build:
	$(DBT) build --project-dir ./$(DBT_DIR) $(PROFILES_ARG)

run_etl:
	uv run python etl/dlt_mssql_to_bigquery.py

dlt_pl_list:
	uv run dlt pipeline --list-pipelines

run_dlt:
	uv run dlt pipeline mssql_to_bigquery sync

full_pipeline: run_etl run_dbt
