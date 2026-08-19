"""Project the manifest into dbt's `sources.yml`.

The manifest is authoritative for column names and types; this renders them into the shape dbt
reads. `--check` in CI fails when the two have drifted, so a regenerated manifest that nobody
projected cannot reach a build.

The body is dumped by PyYAML rather than concatenated by hand: table and column names come from a
source database, and a name containing a YAML metacharacter used to emit broken YAML in silence.
The header stays a literal because its comments and the `external_location` template would not
survive a round trip.
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
      # s3:// in every environment; only the endpoint and credentials differ, and those live in
      # the dbt profile. Nothing here names the store behind the API.
      external_location: "read_parquet('s3://{{ env_var('S3_BUCKET', 'wwi') }}/__PREFIX__/{name}.parquet')"
    tables:
"""

# Indentation of the `tables:` entries under the header above.
TABLE_INDENT = 6


class _IndentedDumper(yaml.SafeDumper):
    """Indent sequences under their key, which PyYAML does not do by default.

    Without this a list nested in a mapping comes back flush with its key, and the generated file
    would differ from the hand-written original in whitespace alone.
    """

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        super().increase_indent(flow, indentless=False)


def render(manifest: dict[str, Any]) -> str:
    """The full file. The snapshot id is a default rather than a literal, so the models and the
    manifest cannot disagree about which snapshot is current -- a new extraction writes a new
    default and `make sources` moves them on -- while SNAPSHOT_ID can point one build at the
    demo fixture."""
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
