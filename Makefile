# Recipes must be indented with a TAB. Spaces make GNU make fail to parse the file.
# `uv run` resolves the environment from uv.lock; no venv activation needed.
DBT_DIR := wide_world_importers_dw
PROFILES_ARG := $(if $(PROFILES_DIR),--profiles-dir $(PROFILES_DIR),)
DBT := uv run dbt
SNAPSHOT_DB := WWI_Snap
EXTRACT_LOGIN := wwi_extract

.PHONY: install deps parse run_dbt test_dbt build snapshot_create snapshot_drop extract manifest verify

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

snapshot_create:
	sqlcmd -S localhost -U sa -C -v SOURCE_DB="WideWorldImporters" -v SNAPSHOT_DB="$(SNAPSHOT_DB)" -v EXTRACT_LOGIN="$(EXTRACT_LOGIN)" -i scripts/mssql/create_source_snapshot.sql

snapshot_drop:
	sqlcmd -S localhost -U sa -C -v SNAPSHOT_DB="$(SNAPSHOT_DB)" -i scripts/mssql/drop_source_snapshot.sql

extract: snapshot_create
	uv run python etl/dlt_mssql_to_parquet.py --snapshot-db $(SNAPSHOT_DB) --output-dir data/raw
	$(MAKE) snapshot_drop
	$(MAKE) manifest

manifest:
	uv run python scripts/generate_manifest.py

verify:
	uv run python scripts/verify_snapshot.py
