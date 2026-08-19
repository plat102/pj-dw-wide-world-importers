"""Environment parsing in warehouse.py. Small functions, but every command depends on them."""

from __future__ import annotations

import pytest

from config.settings import catalog_dsn, data_path, endpoint_url, use_ssl


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "Yes", " true ", "1 "])
def test_ssl_is_on_for_the_accepted_spellings(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("S3_USE_SSL", value)
    assert use_ssl() is True


@pytest.mark.parametrize("value", ["0", "false", "no", "", "off", "yes please"])
def test_everything_else_is_off(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """Anything unrecognised is off. A typo must not silently enable TLS against a local store."""
    monkeypatch.setenv("S3_USE_SSL", value)
    assert use_ssl() is False


def test_ssl_defaults_to_off_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("S3_USE_SSL", raising=False)
    assert use_ssl() is False


def test_endpoint_scheme_follows_ssl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S3_ENDPOINT", "localhost:8333")
    monkeypatch.setenv("S3_USE_SSL", "false")
    assert endpoint_url() == "http://localhost:8333"
    monkeypatch.setenv("S3_USE_SSL", "true")
    assert endpoint_url() == "https://localhost:8333"


def test_catalog_dsn_defaults_match_the_compose_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CATALOG_DB", "CATALOG_HOST", "CATALOG_PORT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CATALOG_USER", "ducklake")
    monkeypatch.setenv("CATALOG_PASSWORD", "secret")
    dsn = catalog_dsn()
    assert "dbname=ducklake" in dsn
    assert "host=localhost" in dsn
    assert "port=55432" in dsn


def test_lake_prefix_defaults_and_is_separate_from_bronze(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lake and the snapshot share a bucket, so the prefixes must not collide."""
    monkeypatch.setenv("S3_BUCKET", "wwi")
    monkeypatch.delenv("LAKE_PREFIX", raising=False)
    assert data_path() == "s3://wwi/lake/"
    assert not data_path().startswith("s3://wwi/bronze")
