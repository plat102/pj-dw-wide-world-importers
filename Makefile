# Recipes must be indented with a TAB. Spaces make GNU make fail to parse the file.
# `uv run` resolves the environment from uv.lock; no venv activation needed.

# make does not read .env by itself; `-include` so a missing one is not fatal. Keep values free
# of `#` -- make truncates the rest of the line.
-include .env
export
DBT_DIR := wide_world_importers_dw
PROFILES_ARG := $(if $(PROFILES_DIR),--profiles-dir $(PROFILES_DIR),)
DBT := uv run dbt
# One definition of the build command; `build` and `build_demo` differ only in what they add to it.
DBT_BUILD = $(DBT) build --project-dir ./$(DBT_DIR) $(PROFILES_ARG)
# Read from the live source in one snapshot-isolation transaction: read-only SELECT is enough.
SOURCE_DB := WideWorldImporters

# The committed fixture. Its id is read from its own manifest, never typed, so the two cannot
# disagree -- and `=` rather than `:=` so nothing shells out until a demo target actually runs.
DEMO_DIR := data/demo
DEMO_MANIFEST := $(DEMO_DIR)/manifest.json
DEMO_SNAPSHOT_ID = $(shell uv run python -c "import json;print(json.load(open('$(DEMO_MANIFEST)'))['snapshot_id'])")

.PHONY: up down clean_storage seed_bronze seed_bronze_empty seed_demo install deps parse build build_demo extract demo demo_fixture manifest sources sources_check verify compare shape compact compact_dry

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

# Zero-row Parquet carrying the manifest's schema. Every model still executes, so a renamed or
# missing column fails on a binder error -- but anything data-dependent passes on no rows, which is
# why this is no longer what CI builds on. Kept for a pure schema-break check.
seed_bronze_empty:
	uv run python -m scripts.seed_bronze --empty

# Publishes the committed fixture and verifies what landed against its own checksums. What CI seeds:
# real rows, so the referential tests have something to fail on.
seed_demo:
	SNAPSHOT_ID=$(DEMO_SNAPSHOT_ID) uv run python -m scripts.seed_bronze --manifest $(DEMO_MANIFEST) --data-dir $(DEMO_DIR)
	SNAPSHOT_ID=$(DEMO_SNAPSHOT_ID) uv run python -m scripts.verify_snapshot --manifest $(DEMO_MANIFEST)

# --- python + dbt -----------------------------------------------------------------------

install:
	uv sync --frozen

deps:
	$(DBT) deps --project-dir ./$(DBT_DIR) $(PROFILES_ARG)

parse:
	$(DBT) parse --project-dir ./$(DBT_DIR) $(PROFILES_ARG)

build:
	$(DBT_BUILD)

# Build over the fixture rather than the shipped snapshot. manifest_path is absolute because DuckDB
# resolves a relative path against the working directory, and the macro that reads it runs wherever
# dbt happens to be invoked from.
build_demo:
	SNAPSHOT_ID=$(DEMO_SNAPSHOT_ID) $(DBT_BUILD) --vars '{"manifest_path": "$(CURDIR)/$(DEMO_MANIFEST)"}'

# data/raw/ is staging, not where the snapshot lives. The published snapshot is on the object
# store under bronze/<snapshot-id>/; this chain ends by putting it there and verifying it landed.
extract:
	uv run python etl/dlt_mssql_to_parquet.py --source-db $(SOURCE_DB)
	$(MAKE) manifest
	$(MAKE) sources
	$(MAKE) seed_bronze

manifest:
	uv run python -m scripts.generate_manifest

# One command from a fresh clone to a queryable star schema, with no source database. Needs git,
# make, uv and a container runtime -- nothing else, and nothing filled in by hand.
demo:
	uv run python -m scripts.demo

# The reduced fixture a fresh clone builds on: real rows, real checksums, ~2.4 MB. Derived from the
# snapshot in data/raw/, so this needs a machine that has run the extraction -- unlike `make demo`,
# which only needs what is committed. Deterministic: two runs produce identical files.
demo_fixture:
	uv run python -m scripts.make_demo_fixture

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
