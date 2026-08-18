# Recipes must be indented with a TAB. Spaces make GNU make fail to parse the file.
# `uv run` resolves the environment from uv.lock; no venv activation needed.

# make does not read .env by itself; `-include` so a missing one is not fatal. Keep values free
# of `#` -- make truncates the rest of the line.
-include .env
export
DBT_DIR := wide_world_importers_dw
PROFILES_ARG := $(if $(PROFILES_DIR),--profiles-dir $(PROFILES_DIR),)
DBT := uv run dbt
# Read from the live source in one snapshot-isolation transaction: read-only SELECT is enough.
SOURCE_DB := WideWorldImporters

.PHONY: up down clean_storage seed_bronze seed_bronze_empty install deps parse build extract manifest sources sources_check verify compare shape compact compact_dry

# --- storage layer ----------------------------------------------------------------------
# Credentials come from .env; an unset one stops the stack rather than guessing a value.

up:
	docker compose up -d --wait
# Creates the bucket and waits on a real round trip. The container healthcheck goes green before
# the volume server can take a write, so without this whatever runs next races the store.
	uv run python -m scripts.wait_for_storage

down:
	docker compose down

# Deletes the bronze layer and the catalog. Separate from `down` because `down -v` by reflex is
# how a snapshot gets thrown away.
clean_storage:
	docker compose down -v

# Puts the local snapshot on the store, then verifies the objects that landed. A count of
# uploaded files says nothing about their contents.
seed_bronze:
	uv run python -m scripts.seed_bronze
	uv run python -m scripts.verify_snapshot

# Zero-row Parquet carrying the manifest's schema. What CI seeds, because the real snapshot is
# not in the repository. A build over it still executes every model, so a column break fails.
seed_bronze_empty:
	uv run python -m scripts.seed_bronze --empty

# --- python + dbt -----------------------------------------------------------------------

install:
	uv sync --frozen

deps:
	$(DBT) deps --project-dir ./$(DBT_DIR) $(PROFILES_ARG)

parse:
	$(DBT) parse --project-dir ./$(DBT_DIR) $(PROFILES_ARG)

build:
	$(DBT) build --project-dir ./$(DBT_DIR) $(PROFILES_ARG)

# data/raw/ is staging, not where the snapshot lives. The published snapshot is on the object
# store under bronze/<snapshot-id>/; this chain ends by putting it there and verifying it landed.
extract:
	uv run python etl/dlt_mssql_to_parquet.py --source-db $(SOURCE_DB)
	$(MAKE) manifest
	$(MAKE) sources
	$(MAKE) seed_bronze

manifest:
	uv run python -m scripts.generate_manifest

# sources.yml is a projection of the manifest. Regenerate after every extraction.
sources:
	uv run python -m scripts.generate_sources

# Fails if sources.yml has drifted from the manifest. For CI and for pre-push.
sources_check:
	uv run python -m scripts.generate_sources --check

verify:
	uv run python -m scripts.verify_snapshot

# Every relation with its row and column count. Exists so no document carries a row count.
shape:
	uv run python -m scripts.warehouse_shape

# Expire old lake snapshots and delete the files they held. Not part of `build`: a store fills up
# over weeks, not per build. The current snapshot never expires.
compact:
	uv run python -m scripts.lake_retention

compact_dry:
	uv run python -m scripts.lake_retention --dry-run

# Two builds of one snapshot must be identical. Names the relation and the column when not.
compare:
	uv run python -m scripts.compare_builds $(if $(PROFILES_DIR),--profiles-dir $(PROFILES_DIR),)
