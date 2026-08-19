"""Every environment variable this project reads, and every path it resolves, in one place.

Two problems this replaces. First, `warehouse.require()` called `sys.exit` from inside a library,
so importing it put a process exit one call away from any caller. Second, the defaults were written
twice -- here and in `profiles.sample.yml` -- and they disagreed: `require("S3_BUCKET")` failed hard
on unset while the dbt profile quietly fell back to `wwi`. The dbt profile still reads the same
variables through `env_var`, but the names and defaults are stated here.

Paths are absolute and derived from this file's location, not from the working directory. Eight
modules used to recompute `REPO_ROOT` for themselves.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from utils.exceptions import ToolingError

# src/config/settings.py -> src/config -> src -> repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DEMO_DIR = DATA_DIR / "demo"
SNAPSHOT_MANIFEST = DATA_DIR / "snapshots" / "manifest.json"
DEMO_MANIFEST = DEMO_DIR / "manifest.json"

DBT_DIR = REPO_ROOT / "wide_world_importers_dw"
TABLES_CONFIG = REPO_ROOT / "src" / "ingestion" / "tables.yml"

TRUTHY = {"1", "true", "yes"}


def require(name: str) -> str:
    """A variable with no sensible default. Raises rather than exits, so a caller can catch it."""
    value = os.environ.get(name)
    if not value:
        raise ToolingError(f"{name} is not set -- copy .env.example to .env and fill it in")
    return value


def optional(name: str, default: str) -> str:
    return os.environ.get(name, default)


def flag(name: str, default: bool = False) -> bool:
    """Anything unrecognised is false: a typo must not quietly turn TLS on for a local store."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUTHY


def use_ssl() -> bool:
    return flag("S3_USE_SSL")


def endpoint_url() -> str:
    return f"{'https' if use_ssl() else 'http'}://{require('S3_ENDPOINT')}"


def bucket() -> str:
    return require("S3_BUCKET")


def lake_prefix() -> str:
    return optional("LAKE_PREFIX", "lake")


def data_path() -> str:
    """Where the lake's own Parquet lives. Shares a bucket with bronze/, never a prefix."""
    return f"s3://{bucket()}/{lake_prefix()}/"


def catalog_dsn() -> str:
    return (
        f"dbname={optional('CATALOG_DB', 'ducklake')} "
        f"host={optional('CATALOG_HOST', 'localhost')} "
        f"port={optional('CATALOG_PORT', '55432')} "
        f"user={require('CATALOG_USER')} "
        f"password={require('CATALOG_PASSWORD')}"
    )


def redact(text: str) -> str:
    """Strip the catalog password out of anything about to be printed.

    `catalog_dsn()` interpolates the password into the ATTACH statement, and dbt echoes that
    statement on failure. This lives next to the function that creates the exposure rather than at
    the call site that noticed it.
    """
    return re.sub(r"password=\S+", "password=***", text)
