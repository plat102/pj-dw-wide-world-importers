"""Where a snapshot's objects live on the store: `bronze/<snapshot-id>/<table>/<file>.parquet`."""

from __future__ import annotations

from datetime import UTC, datetime


def snapshot_id(snapshot_timestamp: str) -> str:
    """`2026-08-16T13:29:42+00:00` -> `20260816T132942Z`. Sortable and filename-safe."""
    moment = datetime.fromisoformat(snapshot_timestamp)
    # Normalised to UTC so one instant always yields one id; naive is taken to be UTC already.
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC).replace(tzinfo=None)
    return moment.strftime("%Y%m%dT%H%M%SZ")


def bronze_prefix(identifier: str) -> str:
    """The snapshot's key prefix, with no bucket and no leading or trailing slash."""
    return f"bronze/{identifier}"


def bronze_prefix_template(manifest: dict) -> str:
    """The same prefix as Jinja, so SNAPSHOT_ID can point one build at another snapshot.

    The default is written from the manifest, so sources.yml cannot name a different one.
    """
    return "bronze/{{ env_var('SNAPSHOT_ID', '" + manifest["snapshot_id"] + "') }}"
