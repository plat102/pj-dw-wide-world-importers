"""Project the manifest into dbt's `sources.yml`.

The manifest is authoritative for column names and types; this renders them into the shape dbt
reads, and `--check` in CI fails when the two have drifted.

The body is dumped by PyYAML, not concatenated, because a name out of the source database may
contain a YAML metacharacter. The header stays a literal: its comments and the
`external_location` template would not survive a round trip.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from contracts.arrow_types import duckdb_type
from contracts.paths import bronze_prefix_template
from utils.exceptions import ToolingError

HEADER = """# GENERATED -- do not hand-edit. Regenerate with `make sources` after a new extraction.
# The manifest is authoritative for column names and types; this file is a projection of it.
version: 2
sources:
  - name: wwi_raw
    description: >
      Wide World Importers OLTP, frozen as a Parquet snapshot on the object store. Row counts,
      sizes and checksums live in data/snapshots/manifest.json, which is authoritative; they are
      not repeated here.
    meta:
      # The endpoint and credentials live in the dbt profile; nothing here names the store.
      # One glob per table: dlt decides how many files a table takes, the folder is the table.
      external_location: "read_parquet('s3://{{ env_var('S3_BUCKET', 'wwi') }}/__PREFIX__/{name}/*.parquet')"
    tables:
"""

# Indentation of the `tables:` entries under the header above.
TABLE_INDENT = 6


class _IndentedDumper(yaml.SafeDumper):
    """Indent sequences under their key, which PyYAML does not do by default."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        super().increase_indent(flow, indentless=False)


def render(manifest: dict[str, Any]) -> str:
    """The full file: the header, with the snapshot id as a default, and the projected tables."""
    tables = [
        {
            "name": table,
            "columns": [
                {"name": column, "data_type": duckdb_type(arrow)}
                for column, arrow in manifest["tables"][table]["columns"].items()
            ],
        }
        for table in sorted(manifest["tables"])
    ]
    body = yaml.dump(
        tables, Dumper=_IndentedDumper, sort_keys=False, default_flow_style=False, width=10_000
    )
    indented = "".join(" " * TABLE_INDENT + line + "\n" for line in body.splitlines())
    return HEADER.replace("__PREFIX__", bronze_prefix_template(manifest)) + indented


def check(manifest: dict[str, Any], output: Path) -> str:
    current = output.read_text(encoding="utf-8") if output.exists() else ""
    if current != render(manifest):
        raise ToolingError(
            f"{output.name} does not match the manifest -- run `make sources` and commit the result"
        )
    return f"{output.name} matches the manifest"


def write(manifest: dict[str, Any], output: Path) -> str:
    output.write_text(render(manifest), encoding="utf-8")
    tables = len(manifest["tables"])
    columns = sum(len(t["columns"]) for t in manifest["tables"].values())
    return f"wrote {output}: {tables} tables, {columns} columns"
