# Recipes must be indented with a TAB. Spaces make GNU make fail to parse the file.
# `uv run` resolves the environment from uv.lock; no venv activation needed.

# make does not read .env by itself; `-include` so a missing one is not fatal. Keep values free
# of `#` -- make truncates the rest of the line.
-include .env
export
# libpq reads the catalog password from here -- for wwi, dlt and dbt alike -- so no connection
# string carries it, and no error can echo it.
export PGPASSWORD := $(CATALOG_PASSWORD)
DBT_DIR := wide_world_importers_dw
# dbt reads the profile from this repository, never from ~/.dbt: a copy in a home directory is
# how a fix that had already landed here -- dropping `password=` -- kept being undone on one
# machine. Override with PROFILES_DIR for a profile kept elsewhere.
PROFILES_ARG := --profiles-dir $(if $(PROFILES_DIR),$(PROFILES_DIR),$(CURDIR))
DBT := uv run dbt
# Every dbt invocation needs both, so they are named once.
DBT_PROJECT = --project-dir ./$(DBT_DIR) $(PROFILES_ARG)
# Read-only SELECT on the source is enough; `extract` never writes to it.
SOURCE_DB := WideWorldImporters

.PHONY: up down clean_storage install parse build extract compare shape catalog lint format typecheck test check

# --- storage layer ----------------------------------------------------------------------
# Credentials come from .env; an unset one stops the stack rather than guessing a value.

up:
	docker compose up -d --wait
# The healthcheck goes green before the volume server can take a write, so wait on a real one.
	uv run wwi wait-storage

down:
	docker compose down

# Deletes the lake and its catalog, raw included. Separate from `down`, which keeps them.
clean_storage:
	docker compose down -v

# --- checks -----------------------------------------------------------------------------
# `check` is what CI runs and what to run before pushing. None of it needs Docker.

check: lint typecheck test

lint:
	uv run ruff check .
# The architectural boundary, checked: nothing outside the source connector may reach the source.
	uv run lint-imports

# Not part of `check`: a wholesale reformat would bury real changes. Here for new code.
format:
	uv run ruff format .

typecheck:
	uv run mypy

test:
	uv run pytest

# --- python + dbt -----------------------------------------------------------------------

install:
	uv sync --frozen

parse:
	$(DBT) parse $(DBT_PROJECT)

build:
	$(DBT) build $(DBT_PROJECT)

# dlt writes into the lake itself, so there is nothing to upload and nothing to project: the
# raw schema is the record of what landed.
extract:
	uv run wwi extract --source-db $(SOURCE_DB)

# Every relation with its row and column count. Exists so no document carries a row count.
shape:
	uv run wwi shape

# Regenerates docs/data_warehouse_catalog.md. The page is output; schema.yml is the source.
catalog:
	uv run wwi catalog > docs/data_warehouse_catalog.md
	@echo "wrote docs/data_warehouse_catalog.md"

# Two builds of one raw load must be identical; names the column when not. Split out from
# `make test` because it costs two full builds.
compare:
	uv run pytest tests/integration/test_build_determinism.py
