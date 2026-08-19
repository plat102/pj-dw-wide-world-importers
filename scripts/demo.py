#!/usr/bin/env python
"""Take a fresh clone to a queryable star schema in one command, with no source database.

Everything this needs is committed: the reduced fixture in data/demo/ and its manifest. The shipped
snapshot is not here and is not required. What is required is git, make, uv and a container runtime.

The fixture's id and manifest path are bound in this one place, so nothing else in the repository
has to know that a second snapshot exists.

    python -m scripts.demo       # or: make demo
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "data" / "demo"
FIXTURE_MANIFEST = FIXTURE_DIR / "manifest.json"
DBT_DIR = REPO_ROOT / "wide_world_importers_dw"
SAMPLE_PROFILE = REPO_ROOT / "profiles.sample.yml"
PROFILE = DBT_DIR / "profiles.yml"

step_number = 0


def step(title: str) -> None:
    global step_number
    step_number += 1
    print(f"\n\033[1m[{step_number}] {title}\033[0m", flush=True)


def run(command: list[str], env: dict[str, str] | None = None) -> None:
    print(f"    $ {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=REPO_ROOT, env=env)
    if result.returncode:
        sys.exit(f"\n{command[0]} failed with exit {result.returncode} -- stopping before the next step")


def load_env() -> dict[str, str]:
    """Read .env into this process so every subprocess inherits it.

    The file wins over the surrounding shell, which is what `-include .env` plus `export` does in the
    Makefile. Matching it matters: a stale S3_ENDPOINT in a shell would otherwise point half the
    steps at one store and half at another.
    """
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env", override=True)
    return dict(os.environ)


def assert_no_source_credential() -> None:
    """The demo must never reach the source. Print it rather than assume it.

    An assumption about a negative is not evidence, and this is the property the whole two-stage
    design rests on: no CI in a real data platform connects to a production OLTP database.
    """
    value = os.environ.get("MSSQL_CONNECTION_STRING", "").strip()
    if value:
        sys.exit(
            "MSSQL_CONNECTION_STRING is set. The demo builds from the committed fixture and must "
            "not be able to reach the source; unset it and run again."
        )
    print("    MSSQL_CONNECTION_STRING is unset -- this build cannot reach the source database")


def assert_lake_is_ours(fixture: dict) -> None:
    """Refuse to write fixture rows into a warehouse built from something else.

    On a machine that has built from the real snapshot, the fixture would land in the same DuckLake
    catalog and nothing downstream would announce which one a query had read. Per-machine isolation
    would need a second Postgres database, and the image only creates one at volume initialisation,
    so this refuses and names the way out instead.

    An empty lake is fine, and so is a lake this fixture already built -- otherwise the demo could
    not be run twice, and being re-runnable is part of what it claims. Provenance is inferred from
    one row count rather than recorded: the fixture's own manifest says how many order lines it
    holds, and the shipped snapshot's count is an order of magnitude larger. The inference can be
    fooled by a coincidence, and the cost of being fooled is rebuilding tables from the fixture,
    which is what the demo does anyway.
    """
    from scripts.warehouse import connect

    probe = "main_stg.stg_sales_order_line"
    expected = fixture["tables"]["sales__order_lines"]["row_count"]
    conn = connect()
    try:
        relations = conn.execute(
            "select count(*) from information_schema.tables where table_catalog = 'lake'"
        ).fetchone()[0]
        if not relations:
            print("    the lake is empty -- nothing to overwrite")
            return
        try:
            found = conn.execute(f"select count(*) from {probe}").fetchone()[0]
        except Exception:
            found = None
    finally:
        conn.close()

    if found == expected:
        print(f"    the lake holds {relations} relations already built from this fixture -- rebuilding")
        return
    sys.exit(
        f"the lake already holds {relations} relation(s) that this fixture did not build "
        f"({probe} has {found if found is not None else 'no'} rows, the fixture has {expected:,}).\n"
        "  The demo would write fixture rows beside them and nothing would say which is which.\n"
        "  Run `make clean_storage` to discard the current warehouse, or run the demo in a fresh "
        "clone."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep-warehouse",
        action="store_true",
        help="skip the provenance guard; the fixture will build beside whatever is already there",
    )
    args = parser.parse_args()

    if not FIXTURE_MANIFEST.exists():
        sys.exit(
            f"{FIXTURE_MANIFEST} is missing. It is committed, so this is a partial checkout rather "
            "than a missing extraction."
        )
    fixture = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
    started = time.monotonic()

    step("Install the pinned environment")
    run(["uv", "sync", "--frozen"])

    step("Make sure there is a .env to read")
    run(["uv", "run", "python", "-m", "scripts.bootstrap_env"])
    env = load_env()
    # sources.yml defaults to the shipped snapshot's prefix; this is what points it at the fixture.
    env["SNAPSHOT_ID"] = fixture["snapshot_id"]
    assert_no_source_credential()

    step("Put a dbt profile where dbt will find it")
    if PROFILE.exists():
        print(f"    {PROFILE.relative_to(REPO_ROOT)} already exists -- leaving it alone")
    else:
        PROFILE.write_text(SAMPLE_PROFILE.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"    copied {SAMPLE_PROFILE.name} to {PROFILE.relative_to(REPO_ROOT)}")

    # dbt_packages/ is git-ignored and four models call dbt_utils, so a clone has the dependency
    # declared and not installed. Missing this step stops the build at Parse with a message about
    # packages, which reads like a broken repository rather than a step nobody ran.
    step("Install the dbt packages the models import")
    run(
        ["uv", "run", "dbt", "deps", "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)],
        env=env,
    )

    step("Bring up the object store and the DuckLake catalog")
    run(["make", "up"], env=env)

    step("Check the lake is empty, or ours")
    if args.keep_warehouse:
        print("    skipped by --keep-warehouse")
    else:
        os.environ.update(env)
        assert_lake_is_ours(fixture)

    step(f"Publish the fixture to the store as {fixture['snapshot_id']}")
    run(
        [
            "uv", "run", "python", "-m", "scripts.seed_bronze",
            "--manifest", str(FIXTURE_MANIFEST),
            "--data-dir", str(FIXTURE_DIR),
        ],
        env=env,
    )

    step("Verify what landed against the fixture's own checksums")
    run(
        ["uv", "run", "python", "-m", "scripts.verify_snapshot", "--manifest", str(FIXTURE_MANIFEST)],
        env=env,
    )

    step("Build the warehouse and run every test")
    run(
        [
            "uv", "run", "dbt", "build",
            "--project-dir", str(DBT_DIR),
            "--profiles-dir", str(DBT_DIR),
            # Absolute, because DuckDB resolves a relative path against the working directory and
            # the macro that reads this runs wherever dbt happens to be invoked from.
            "--vars", json.dumps({"manifest_path": str(FIXTURE_MANIFEST)}),
        ],
        env=env,
    )

    step("Report what was built")
    run(["uv", "run", "python", "-m", "scripts.warehouse_shape"], env=env)

    elapsed = time.monotonic() - started
    catalog_port = env.get("CATALOG_PORT", "55432")
    print(
        f"\n\033[1mDone in {elapsed:.0f}s.\033[0m The warehouse is a DuckLake lakehouse: Parquet on "
        "the object store, catalog in Postgres.\n"
        "\nQuery it from anything that speaks DuckDB. The shortest route:\n"
        "    uv run python -c \"from scripts.warehouse import connect; "
        "print(connect().sql('select count(*) from main_mart.mart_sales_order_line'))\"\n"
        f"\nFor a SQL client, attach the catalog on port {catalog_port} and the bucket over the S3 "
        "API; `make shape` above prints every relation it will see.\n"
        "\nThis was built from the committed demo fixture, not the full snapshot -- so the row "
        "counts are the fixture's. With the real snapshot in data/raw/, `make extract` publishes it "
        "and `make build` produces the warehouse in full."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
