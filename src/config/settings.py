"""Every environment variable this project reads and every path it resolves, in one place.

The dbt profile reads the same variables through `env_var`; the names and defaults are stated here.
Paths are derived from this file's location, so they do not depend on the working directory.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

from utils.exceptions import ToolingError

# src/config/settings.py -> src/config -> src -> repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

DBT_DIR = REPO_ROOT / "wide_world_importers_dw"
TABLES_CONFIG = REPO_ROOT / "src" / "ingestion" / "tables.yml"

# The lake schema `make extract` writes and dbt's sources read.
RAW_SCHEMA = "raw"
# The schema holding the lake's catalog tables. dlt and dbt must name the same one, or each
# attaches a lake of its own inside one Postgres.
METADATA_SCHEMA = "public"

TRUTHY = {"1", "true", "yes"}


def require(name: str) -> str:
    """A variable with no sensible default. Raises rather than exits, so a caller can catch it."""
    value = os.environ.get(name)
    if not value:
        raise ToolingError(f"{name} is not set -- set it in .env and run through make")
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


def endpoint() -> str:
    return optional("S3_ENDPOINT", "localhost:8333")


def endpoint_url() -> str:
    return f"{'https' if use_ssl() else 'http'}://{endpoint()}"


def bucket() -> str:
    return optional("S3_BUCKET", "wwi")


def lake_prefix() -> str:
    return optional("LAKE_PREFIX", "lake")


def data_path() -> str:
    """The lake root. Every layer lives in it, raw included, as schemas of one catalog."""
    return f"s3://{bucket()}/{lake_prefix()}/"


def catalog_dsn() -> str:
    """The catalog in libpq form. No password here or in `catalog_url`: libpq reads PGPASSWORD,
    which the Makefile sets from CATALOG_PASSWORD.

    Both strings land in DuckDB's error messages, which dbt and dlt print and dbt also logs. Out
    of them, the password is never echoed and needs no quoting.
    """
    return (
        f"dbname={optional('CATALOG_DB', 'ducklake')} "
        f"host={optional('CATALOG_HOST', 'localhost')} "
        f"port={optional('CATALOG_PORT', '55432')} "
        f"user={require('CATALOG_USER')}"
    )


def catalog_url() -> str:
    """The catalog as a URL, the only form dlt parses. Same database as `catalog_dsn`."""
    return (
        f"postgresql://{quote(require('CATALOG_USER'), safe='')}"
        f"@{optional('CATALOG_HOST', 'localhost')}:{optional('CATALOG_PORT', '55432')}"
        f"/{optional('CATALOG_DB', 'ducklake')}"
    )
