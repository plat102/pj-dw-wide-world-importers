"""Where a snapshot's objects live on the store: `bronze/<snapshot-id>/<table>.parquet`.

The id makes a new extraction land beside the previous one rather than overwrite it.
"""

from __future__ import annotations

from datetime import datetime, timezone


def snapshot_id(snapshot_timestamp: str) -> str:
    """`2026-08-16T13:29:42+00:00` -> `20260816T132942Z`. Sortable and filename-safe."""
    moment = datetime.fromisoformat(snapshot_timestamp)
    # Normalised to UTC so one instant always yields one id; naive is taken to be UTC already.
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment.strftime("%Y%m%dT%H%M%SZ")


def bronze_prefix(manifest: dict) -> str:
    """The snapshot's key prefix, with no bucket and no leading or trailing slash."""
    return f"bronze/{manifest['snapshot_id']}"


def bronze_prefix_template(manifest: dict) -> str:
    """The same prefix as Jinja, with this manifest's id as the default.

    sources.yml renders through this so one repository can address two snapshots -- the shipped one
    and the committed demo fixture -- without the models knowing which they read. The default is
    written from the manifest rather than typed, so the generated file still cannot disagree with
    the manifest it was generated from.
    """
    return "bronze/{{ env_var('SNAPSHOT_ID', '" + manifest["snapshot_id"] + "') }}"
