"""Environment parsing in config.settings. Small functions, but every command depends on them."""

from __future__ import annotations

from urllib.parse import unquote, urlsplit

import pytest

from config.settings import catalog_dsn, catalog_url, data_path, endpoint_url, use_ssl


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
    dsn = catalog_dsn()
    assert "dbname=ducklake" in dsn
    assert "host=localhost" in dsn
    assert "port=55432" in dsn


def test_no_connection_string_carries_the_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both strings end up in error messages, so neither may carry the password."""
    monkeypatch.setenv("CATALOG_USER", "ducklake")
    monkeypatch.setenv("CATALOG_PASSWORD", "it's a b")
    assert "it's a b" not in catalog_dsn()
    assert urlsplit(catalog_url()).password is None


def test_catalog_url_quotes_a_reserved_character(monkeypatch: pytest.MonkeyPatch) -> None:
    """The user is still interpolated into a URL. Unquoted, a `/` or `@` in it truncates it."""
    monkeypatch.setenv("CATALOG_USER", "wwi@lake/rw")
    url = catalog_url()
    assert "wwi%40lake%2Frw" in url
    assert unquote(urlsplit(url).username or "") == "wwi@lake/rw"


def test_data_path_is_the_lake_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """dlt's DATA_PATH and dbt's data_path are this string. A missing slash makes two lakes."""
    monkeypatch.setenv("S3_BUCKET", "wwi")
    monkeypatch.delenv("LAKE_PREFIX", raising=False)
    assert data_path() == "s3://wwi/lake/"


def test_catalog_url_and_dsn_reach_one_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """dlt is handed a URL and duckdb a libpq string; they must name the same catalog."""
    for name in ("CATALOG_DB", "CATALOG_HOST", "CATALOG_PORT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CATALOG_USER", "ducklake")
    parts = urlsplit(catalog_url())
    assert parts.hostname == "localhost"
    assert str(parts.port) == "55432"
    assert parts.path == "/ducklake"
    assert parts.username == "ducklake"
    assert "dbname=ducklake" in catalog_dsn()
