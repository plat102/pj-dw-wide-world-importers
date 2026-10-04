# Recipes must be indented with a TAB. Spaces make GNU make fail to parse the file.
# `uv run` resolves the environment from uv.lock; no venv activation needed.

# make does not read .env by itself; `-include` so a missing one is not fatal. Keep values free
# of `#`, where make truncates the rest of the line, and of `$`, which make expands.
-include .env
# Named, not a bare `export`: that handed every variable in .env to every recipe, so dbt ran with
# the source credential in its environment. These are what wwi and the dbt profile read, and
# tests/unit/test_make_env.py fails when the code reads one this list lacks. A name left unset
# is not exported at all, so the code's default applies rather than an empty string.
LAKE_ENV := S3_ACCESS_KEY S3_SECRET_KEY S3_ENDPOINT S3_BUCKET S3_USE_SSL LAKE_PREFIX \
	CATALOG_USER CATALOG_DB CATALOG_HOST CATALOG_PORT
export $(foreach v,$(LAKE_ENV),$(if $(filter undefined,$(origin $(v))),,$(v)))
# The source credential reaches `extract` and nothing else -- not even when it comes from the
# shell rather than .env. See the target-specific export on `extract`.
unexport MSSQL_CONNECTION_STRING
# Same for the catalog reader's password: it reaches `catalog_reader` and nothing else.
unexport CATALOG_READER_PASSWORD
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

.PHONY: up down clean_storage catalog_reader install parse build extract compare shape catalog maintain raw_schema build_empty score lineage lint format typecheck test check

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

# A catalog login that can only SELECT, for BI tools. The store's matching read-only identity comes
# from S3_READER_ACCESS_KEY at `make up`. Re-runnable. `public` is DuckLake's metadata schema here
# (settings.METADATA_SCHEMA).
catalog_reader: export CATALOG_READER_PASSWORD := $(CATALOG_READER_PASSWORD)
catalog_reader:
	$(if $(and $(CATALOG_READER_USER),$(CATALOG_READER_PASSWORD)),,$(error set CATALOG_READER_USER and CATALOG_READER_PASSWORD in .env))
	docker compose exec -T -e CATALOG_READER_PASSWORD catalog \
		psql -q -U "$(CATALOG_USER)" -d "$(or $(CATALOG_DB),ducklake)" \
		-v reader="$(CATALOG_READER_USER)" -v owner="$(CATALOG_USER)" -v metadata_schema=public \
		< infrastructure/postgres/create_catalog_reader.sql
	@echo "catalog reader $(CATALOG_READER_USER) can SELECT the lake's metadata"

# --- checks -----------------------------------------------------------------------------
# `check` is what CI runs and what to run before pushing. None of it needs Docker.

check: lint typecheck test build_empty score

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

# The load gate runs on its own first. In `dbt build`, a failing test on a source does not skip
# the models that read it, so a half-finished load would still be built into core and marts.
build:
	$(DBT) test $(DBT_PROJECT) --select "test_name:complete_dlt_load"
	$(DBT) build $(DBT_PROJECT)

# dlt writes into the lake itself, so there is nothing to upload and nothing to project: the
# raw schema is the record of what landed.
extract: export MSSQL_CONNECTION_STRING := $(MSSQL_CONNECTION_STRING)
extract:
	uv run wwi extract --source-db $(SOURCE_DB)

# Every relation with its row and column count. Exists so no document carries a row count.
shape:
	uv run wwi shape

# Regenerates docs/data_warehouse_catalog.md. The page is output; schema.yml is the source.
# `parse` first, so the descriptions come from the current manifest. Written to a temporary file
# and moved on success: a redirect straight onto the page empties it whenever the command fails.
catalog: parse
	uv run wwi catalog > docs/data_warehouse_catalog.md.tmp \
		&& mv docs/data_warehouse_catalog.md.tmp docs/data_warehouse_catalog.md \
		|| { rm -f docs/data_warehouse_catalog.md.tmp; exit 1; }
	@echo "wrote docs/data_warehouse_catalog.md"

# Every model and every test, built on a local lake that holds the raw schema and no rows: the
# SQL runs against the engine, so a misspelt column or a broken contract fails here, not after
# `make extract`. No stack and no source. The two tests that exist to fail on empty tables --
# the load gate and not_empty -- are the only ones left out.
build_empty:
	uv run wwi empty-lake
	$(DBT) build $(DBT_PROJECT) --target empty --empty \
		--exclude "test_name:complete_dlt_load test_name:not_empty"

# Governance rules on the manifest: personal data classified where it is published. Rules live in
# $(DBT_DIR)/dbt_score_rules/. Reads the manifest the last dbt command wrote, which in `check` is
# build_empty's, so it needs no stack and no .env.
score:
	uv run dbt-score lint --manifest $(DBT_DIR)/target/manifest.json

# Column-level lineage as a static page, from dbt's manifest and catalog: which raw column feeds
# which published one. Built on the empty lake, so no stack: lineage comes from the SQL, and the
# empty lake has the real column types. Output stays in target/, never committed. The page bundles
# an analytics library; --disable-telemetry and DO_NOT_TRACK keep it from loading.
lineage: build_empty
	$(DBT) docs generate $(DBT_PROJECT) --target empty
	DO_NOT_TRACK=1 uv run colibri generate --disable-telemetry \
		--manifest $(DBT_DIR)/target/manifest.json --catalog $(DBT_DIR)/target/catalog.json \
		--output-dir $(DBT_DIR)/target/lineage
	@echo "open $(DBT_DIR)/target/lineage/index.html"

# Regenerates src/ingestion/raw_schema.sql from the loaded lake. Run it after changing
# tables.yml and extracting; the diff is the change to the raw schema, reviewed like code.
raw_schema:
	uv run wwi raw-schema > src/ingestion/raw_schema.sql.tmp \
		&& mv src/ingestion/raw_schema.sql.tmp src/ingestion/raw_schema.sql \
		|| { rm -f src/ingestion/raw_schema.sql.tmp; exit 1; }
	@echo "wrote src/ingestion/raw_schema.sql"

# Expires snapshots older than KEEP_DAYS, merges small files, and deletes the files no kept
# snapshot reads. The newest snapshot always survives. Never while `extract` or `build` runs:
# DuckLake commits from two writers conflict. `make maintain DRY_RUN=1` only reports.
KEEP_DAYS ?= 7
maintain:
	uv run wwi maintain --keep-days $(KEEP_DAYS) $(if $(DRY_RUN),--dry-run)

# Two builds of one raw load must be identical; names the column when not. Not part of `make
# test`, which deselects integration tests, because it costs two full builds. `--require-lake`
# turns "lake unreachable" or "raw empty" into a failure: here, a skip would read as a pass.
compare:
	uv run pytest -m integration --require-lake tests/integration/test_build_determinism.py
