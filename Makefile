# Recipes must be indented with a TAB. Spaces make GNU make fail to parse the file.
# `uv run` resolves the environment from uv.lock; no venv activation needed.
DBT_DIR := wide_world_importers_dw
PROFILES_ARG := $(if $(PROFILES_DIR),--profiles-dir $(PROFILES_DIR),)
DBT := uv run dbt
SNAPSHOT_DB := WWI_Snap
EXTRACT_LOGIN := wwi_extract

.PHONY: install deps parse run_dbt test_dbt build snapshot_create snapshot_drop extract manifest sources sources_check verify compare shape

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
	$(MAKE) sources

manifest:
	uv run python scripts/generate_manifest.py

# sources.yml is a projection of the manifest. Regenerate after every extraction.
sources:
	uv run python scripts/generate_sources.py

# Fails if sources.yml has drifted from the manifest. For CI and for pre-push.
sources_check:
	uv run python scripts/generate_sources.py --check

verify:
	uv run python scripts/verify_snapshot.py

# Every relation with its row and column count. Exists so no document carries a row count.
shape:
	uv run python scripts/warehouse_shape.py

# Two builds of one snapshot must be identical. Names the relation and the column when not.
compare:
	uv run python scripts/compare_builds.py $(if $(PROFILES_DIR),--profiles-dir $(PROFILES_DIR),)
