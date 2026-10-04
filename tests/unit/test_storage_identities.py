"""The store's identities, rendered the way the container renders them at `make up`.

The read-only identity is what a BI tool gets. If it rendered with a write action, or rendered at
all with an empty key, the store would hand that tool more than it is meant to have.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

import pytest

from config import settings

SEAWEEDFS = settings.REPO_ROOT / "infrastructure" / "seaweedfs"

pytestmark = pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")


def _render(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(SEAWEEDFS / "render-identities.sh")],
        input=(SEAWEEDFS / "s3-identities.template.json").read_text(encoding="utf-8"),
        env={"PATH": "/usr/bin:/bin", **env},
        capture_output=True,
        text=True,
        check=False,
    )


def _identities(env: dict[str, str]) -> dict[str, dict[str, Any]]:
    rendered = _render(env)
    assert rendered.returncode == 0, rendered.stderr
    return {identity["name"]: identity for identity in json.loads(rendered.stdout)["identities"]}


ADMIN = {"S3_ACCESS_KEY": "admin-key", "S3_SECRET_KEY": "admin-secret"}
READER = {"S3_READER_ACCESS_KEY": "reader-key", "S3_READER_SECRET_KEY": "reader-secret"}


def test_without_a_reader_key_only_the_admin_exists() -> None:
    assert set(_identities(ADMIN)) == {"wwi"}


def test_the_reader_can_only_read_and_list_its_bucket() -> None:
    identities = _identities({**ADMIN, **READER, "S3_BUCKET": "lakebucket"})
    reader = identities["wwi_reader"]
    assert reader["credentials"] == [{"accessKey": "reader-key", "secretKey": "reader-secret"}]
    assert reader["actions"] == ["Read:lakebucket", "List:lakebucket"]
    assert identities["wwi"]["credentials"][0]["accessKey"] == "admin-key"


def test_a_reader_key_without_its_secret_stops_the_store() -> None:
    rendered = _render({**ADMIN, "S3_READER_ACCESS_KEY": "reader-key"})
    assert rendered.returncode != 0
    assert "S3_READER_SECRET_KEY" in rendered.stderr


def test_no_placeholder_or_marker_survives_rendering() -> None:
    for env in (ADMIN, {**ADMIN, **READER}):
        rendered = _render(env)
        assert "__" not in rendered.stdout
        assert "#reader" not in rendered.stdout
