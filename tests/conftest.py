"""Shared pytest options."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--require-lake",
        action="store_true",
        help="fail, rather than skip, integration tests when the lake is unreachable or empty",
    )
