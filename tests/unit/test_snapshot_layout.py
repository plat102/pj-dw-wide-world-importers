"""The snapshot id is what every bronze prefix is built from, so its edge cases are pinned here."""

from __future__ import annotations

import pytest

from scripts.snapshot_layout import bronze_prefix, bronze_prefix_template, snapshot_id


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        # Already UTC, with and without the Z spelling.
        ("2026-08-18T12:58:22+00:00", "20260818T125822Z"),
        ("2026-08-18T12:58:22Z", "20260818T125822Z"),
        # Offset timestamps are converted, not truncated: +07:00 is seven hours ahead of UTC, so
        # the same instant is 05:58 UTC and the date is unchanged.
        ("2026-08-18T12:58:22+07:00", "20260818T055822Z"),
        # An offset that crosses midnight must move the date too.
        ("2026-08-18T02:00:00+07:00", "20260817T190000Z"),
    ],
)
def test_offsets_are_converted_to_utc(timestamp: str, expected: str) -> None:
    assert snapshot_id(timestamp) == expected


def test_naive_timestamps_are_read_as_utc_not_local() -> None:
    """A naive timestamp is taken as UTC already, so it must not shift with the machine's zone."""
    assert snapshot_id("2026-08-18T12:58:22") == snapshot_id("2026-08-18T12:58:22+00:00")


def test_bronze_prefix_has_no_bucket_and_no_slashes() -> None:
    prefix = bronze_prefix({"snapshot_id": "20260818T125822Z"})
    assert prefix == "bronze/20260818T125822Z"
    assert not prefix.startswith("/") and not prefix.endswith("/")
    assert "s3://" not in prefix


def test_prefix_template_defaults_to_the_manifest_id() -> None:
    """The template is rendered into sources.yml, so the manifest's id must be its default --
    otherwise a build with SNAPSHOT_ID unset reads a different snapshot than the manifest names."""
    template = bronze_prefix_template({"snapshot_id": "20260818T125822Z"})
    assert "env_var('SNAPSHOT_ID', '20260818T125822Z')" in template
    assert template.startswith("bronze/")
