# AGENTS.md — Wide World Importers Data Warehouse

A Kimball star schema over the Wide World Importers sample OLTP: dlt loads SQL Server into the `raw` schema of a DuckLake lakehouse, and dbt builds `staging`, `core` and `marts` from it. Human entry point: [README.md](README.md).

## Commands

Run everything from the repository root; `uv run` needs no activated venv.

```bash
make install                              # uv sync --frozen
make check                                # THE gate: ruff, import contracts, mypy, pytest, build_empty. No Docker, no .env. CI runs exactly this
uv run pytest tests/unit/test_raw_schema.py -k name   # one Python test
make parse                                # dbt Jinja and YAML errors only, in seconds
make build_empty                          # every dbt model, data test and unit test on an empty raw schema
uv run ruff format path/to/file.py       # format only the files you wrote; `make format` reformats the whole repo
```

Need the stack (`make up`, Docker) and a filled `.env`: `make build`, `make shape`, `make compare`, `make catalog`, `make raw_schema`. Before reporting a change done, `make check` is green.

## Where does X live?

| Question | Path |
|---|---|
| Which source tables and columns raw carries | `src/ingestion/tables.yml` |
| The extraction (the only code that reaches the source) | `src/ingestion/pipeline.py`, `src/connectors/mssql.py` |
| Every environment variable the code reads | `src/config/settings.py` (`require`, `optional`, `flag`) |
| The `wwi` command behind the make targets | `src/cli/app.py` |
| dbt models, tests, macros | `wide_world_importers_dw/` (run through `make`, never `dbt` from inside it) |
| dbt sources over raw | `wide_world_importers_dw/models/staging/wide_world_importers/__sources.yml` |
| The dbt profile | `profiles.yml` at the root; `make` passes `--profiles-dir` |
| Import contracts, ruff, mypy, pytest config | `pyproject.toml` |
| CI | `.github/workflows/build.yml` |

## Conventions

- Only `ingestion.pipeline` and `connectors.mssql` may import `dlt`, `sqlalchemy` or `pymssql` — the source credential must not be reachable from the transform half. `make lint` checks the modules named in `source_modules` of `[tool.importlinter]` in `pyproject.toml`, not whole packages: a new module under `src/ingestion/` or `src/connectors/` is unguarded until it is added there.
- `src/cli/app.py` imports each subcommand's dependencies inside the function — keeps the source driver off the default import path. Do not hoist them.
- Read an environment variable only through `src/config/settings.py`, and add any new one to `LAKE_ENV` in `Makefile:11` — make hands recipes only the names listed there. `tests/unit/test_make_env.py` fails when the two drift.
- A new source table changes `tables.yml`, `__sources.yml`, `raw_schema.sql` and the model that reads it in one commit — raw carries exactly what a model reads. `tests/unit/test_source_contract.py` and `tests/unit/test_raw_schema.py` enforce it, so `make check` stays red from the `tables.yml` edit until `make raw_schema` has run after an extract. Workflow: `.claude/skills/add-source-table/SKILL.md`.
- dbt naming, folders, SQL style (lowercase, leading commas, one column per line) and required tests: [docs/naming_convention.md](docs/naming_convention.md). New model workflow: `.claude/skills/add-dbt-model/SKILL.md`.
- Give every `ref` in a `from` or `join` an alias and qualify columns with it — under `--empty` dbt renders a ref as an unnamed subquery, so `make build_empty` fails otherwise.
- A test is trusted only after it has been seen to fail: break what it guards, watch it go red, restore.
- Repository text is English only. Markdown prose is never hard-wrapped: one paragraph or bullet per line.
- No row counts, model counts, test counts or sizes in docs, comments or YAML descriptions — they go stale. Name the command that measures it (`make shape`).
- Commits: `<gitmoji> type(scope): subject`, lowercase imperative, as in `git log --oneline`.

## Landmines

- **Load gate runs first** — inside `dbt build` a failing source test does not skip the models downstream, so `make build` runs `complete_dlt_load` on its own first (`Makefile:78`). Keep that order when touching `build`.
- **`dim_date` under `--empty`** — it is generated, not read from raw, so a test that needs its rows reads it through `{{ ref('dim_date').render() }}` (`wide_world_importers_dw/tests/assert_dim_date_calendar.sql:33`), or `build_empty` hands it zero rows.
- **Mart columns are a contract** — `obt_sales_order_line` is `contract: enforced` (`wide_world_importers_dw/models/marts/sales/_sales__models.yml:13`). Changing its columns means changing that YAML in the same commit.
- **`.env` values** — make reads `.env` itself (`Makefile:6`): a `#` truncates a value, a `$` is expanded, and quote marks stay part of it (`settings.require` refuses a quoted value).
- **Integration tests are deselected** — plain `pytest` skips `-m integration`; `make compare` runs them and builds twice against the live lake.

## Boundaries

- Never read, print or edit `.env`; change `.env.example` and tell the user.
- Ask before `make extract` (reads the source database), `make maintain` (deletes snapshot files), `make clean_storage` (deletes the lake), `make compare` (builds twice into the live lake) or `docker compose down`.
- Never hand-edit generated files: `docs/data_warehouse_catalog.md` (`make catalog`), `src/ingestion/raw_schema.sql` (`make raw_schema`), `uv.lock` (`uv lock`).
- Do not hand `MSSQL_CONNECTION_STRING` to any recipe other than `extract` (`Makefile:16`, `Makefile:84`).
- Do not commit or push unless asked.

## More context

| Need | Read |
|---|---|
| Architecture, stack, why the boundary exists | [docs/technical_design.md](docs/technical_design.md) |
| Grain, keys, the bus matrix | [docs/data_modelling.md](docs/data_modelling.md) |
| Every column of every table (generated) | [docs/data_warehouse_catalog.md](docs/data_warehouse_catalog.md) — only when a task names a column |
| What is built, what is not, SCD position | [docs/project_roadmap.md](docs/project_roadmap.md) |
| dbt project layout and its tests | [wide_world_importers_dw/README.md](wide_world_importers_dw/README.md) |
